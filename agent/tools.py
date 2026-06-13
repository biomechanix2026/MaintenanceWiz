"""
The tool suite for the Consolidated Brain.

Every tool returns a rich structured object (not a bare string), echoing the
"smart tools" principle: the ML tool returns RUL + failure prob + SHAP; the RAG
tool returns matched SOP sections tagged to the asset; the ERP tool returns
stock + lead time + alternatives; the SQL tool returns the exact SQL it ran so
engineers can validate it ("AI to build, UI to validate").

These functions are pure Python and individually testable. The orchestrator
exposes them to Claude as tool definitions, and the deterministic fallback
calls them directly in pipeline order.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
import difflib
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from config import SENSOR_FEATURES, RISK_WEIGHTS, PRIORITY_BANDS, MAX_RUL_DAYS
from ml.model import load_model
from knowledge.rag import load_index

# --------------------------------------------------------------------------
# Lazy singletons (load once, reuse)
# --------------------------------------------------------------------------
_MODEL = None
_RAG = None

def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = load_model()
    return _MODEL

def _rag():
    global _RAG
    if _RAG is None:
        _RAG = load_index()
    return _RAG

def _registry():
    return pd.read_csv(C.ASSET_REGISTRY_CSV)

def _latest_readings(asset_id, window=5):
    """Average the last `window` readings to suppress single-sample sensor noise."""
    s = pd.read_csv(C.SENSOR_LOGS_CSV)
    s = s[s.asset_id == asset_id].sort_values("timestamp")
    if s.empty:
        return None
    recent = s.tail(window)
    return {f: round(float(recent[f].mean()), 2) for f in SENSOR_FEATURES}


# ==========================================================================
# In-memory SQL database (transparency: the agent writes SQL, UI can read it)
# ==========================================================================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        for name, path in [("assets", C.ASSET_REGISTRY_CSV),
                           ("sensors", C.SENSOR_LOGS_CSV),
                           ("delays", C.DELAY_LOGS_CSV),
                           ("incidents", C.INCIDENTS_CSV),
                           ("parts", C.PARTS_CSV)]:
            if os.path.exists(path):
                pd.read_csv(path).to_sql(name, self.conn, index=False, if_exists="replace")

    def run(self, sql, max_rows=2000):
        cur = self.conn.execute(sql)
        cols = [d[0] for d in cur.description]
        # cap the fetch so a future larger dataset can't create memory pressure
        return [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]

_DB = None
def _db():
    global _DB
    if _DB is None:
        _DB = Database()
    return _DB


# ==========================================================================
# TOOL 0: Asset resolution / fuzzy matching (runs before everything)
# ==========================================================================
def resolve_asset(query: str) -> dict:
    """Map free-text / jargon / abbreviations to a formal asset_id."""
    aliases = json.load(open(C.ALIASES_JSON))
    reg = _registry()
    q = query.lower().strip()

    # 1. exact asset_id mention
    for aid in reg.asset_id:
        if aid.lower() in q:
            return {"asset_id": aid, "confidence": 1.0, "matched_on": "explicit id"}

    # 2. exact alias substring
    for alias, aid in aliases.items():
        if alias in q:
            return {"asset_id": aid, "confidence": 0.95, "matched_on": f"alias '{alias}'"}

    # 3. fuzzy alias match
    best = difflib.get_close_matches(q, list(aliases.keys()), n=1, cutoff=0.6)
    if best:
        return {"asset_id": aliases[best[0]], "confidence": 0.75,
                "matched_on": f"fuzzy alias '{best[0]}'"}

    # 4. fuzzy against asset names
    names = {r["name"].lower(): r["asset_id"] for _, r in reg.iterrows()}
    best = difflib.get_close_matches(q, list(names), n=1, cutoff=0.5)
    if best:
        return {"asset_id": names[best[0]], "confidence": 0.6,
                "matched_on": f"fuzzy name '{best[0]}'"}

    return {"asset_id": None, "confidence": 0.0, "matched_on": None,
            "clarification_needed": True,
            "candidates": reg[["asset_id", "name"]].to_dict("records")[:6]}


# ==========================================================================
# TOOL 1: Prognostic ML (RUL + failure probability + SHAP attribution)
# ==========================================================================
def prognostic_tool(asset_id: str) -> dict:
    readings = _latest_readings(asset_id)
    reg = _registry()
    row = reg[reg.asset_id == asset_id]
    if readings is None or row.empty:
        return {"error": f"No sensor data for {asset_id}"}
    atype = row.iloc[0]["type"]
    m = _model()
    rul = m.predict_rul(atype, readings)
    prob = m.failure_probability(atype, readings)
    explain = m.explain(atype, readings)
    benchmark = None
    bench_path = os.path.join(C.ML_ARTIFACTS_DIR, "benchmark.json")
    if os.path.exists(bench_path):
        try:
            with open(bench_path, encoding="utf-8") as bf:
                benchmark = json.load(bf)
        except Exception:
            benchmark = None
    out = {
        "asset_id": asset_id,
        "asset_type": atype,
        "latest_readings": readings,
        "rul_days": round(rul, 1),
        "failure_probability_30d": round(prob, 3),
        "shap": explain,
    }
    if benchmark:
        out["model_benchmark"] = benchmark
    return out


def fault_mode_tool(air_temperature_K: float, process_temperature_K: float,
                    rotational_speed_rpm: float, torque_Nm: float,
                    tool_wear_min: float, machine_type: str = "M") -> dict:
    """Classify AI4I-style failure risk and probable failure mode.

    This is an on-demand evidence tool. It degrades gracefully when the optional
    trained artifact or sklearn-backed model cannot be loaded.
    """
    path = os.path.join(C.ML_ARTIFACTS_DIR, "fault_model.pkl")
    if not os.path.exists(path):
        return {"available": False,
                "error": "fault classifier not trained - run: python -m ml.fault"}
    try:
        from ml.fault import load_fault_model, classify_fault
        bundle = load_fault_model(path)
        res = classify_fault(bundle, {
            "Type": machine_type,
            "Air temperature [K]": air_temperature_K,
            "Process temperature [K]": process_temperature_K,
            "Rotational speed [rpm]": rotational_speed_rpm,
            "Torque [Nm]": torque_Nm,
            "Tool wear [min]": tool_wear_min,
        })
        return {"available": True, **res,
                "basis": "AI4I 2020 (UCI 601) analogue; TWF/RNF near-random in source data"}
    except Exception as e:
        return {"available": False, "error": f"{type(e).__name__}: {e}"}


# ==========================================================================
# TOOL 2: Independent abnormality detection (dynamic early warning)
# ==========================================================================
def _deviations(asset_type: str, readings: dict) -> dict:
    nom = C.NOMINAL[asset_type]
    return {
        f: round(float((readings[f] - nom[f][0]) / nom[f][1]), 2)
        for f in SENSOR_FEATURES
    }


def abnormality_tool(asset_id: str, window: int = 5, baseline_window: int = 24) -> dict:
    """Detect abnormal sensor states independently of the RUL model.

    The prognostic model answers "how much life is left?" This rule-based
    detector answers "are the current readings abnormal right now?" using
    z-score deviations from the config-owned NOMINAL baselines plus short-window
    trend. It is intentionally additive and does not alter priority_score.
    """
    reg = _registry()
    row = reg[reg.asset_id == asset_id]
    sensors = pd.read_csv(C.SENSOR_LOGS_CSV)
    g = sensors[sensors.asset_id == asset_id].sort_values("timestamp")
    if row.empty or g.empty:
        return {"asset_id": asset_id, "error": f"No sensor data for {asset_id}"}

    asset_type = row.iloc[0]["type"]
    criticality = int(row.iloc[0]["criticality"])
    recent = g.tail(window)
    prior = g.iloc[max(0, len(g) - window - baseline_window):len(g) - window]

    current = {f: round(float(recent[f].mean()), 2) for f in SENSOR_FEATURES}
    deviations = _deviations(asset_type, current)

    trends = {}
    if not prior.empty:
        prior_readings = {f: round(float(prior[f].mean()), 2) for f in SENSOR_FEATURES}
        prior_devs = _deviations(asset_type, prior_readings)
        trends = {f: round(deviations[f] - prior_devs[f], 2) for f in SENSOR_FEATURES}

    breaches = []
    for f, z in deviations.items():
        abs_z = abs(z)
        if abs_z < C.ANOMALY_WARNING_Z:
            continue
        level = "CRITICAL" if abs_z >= C.ANOMALY_CRITICAL_Z else "WARNING"
        nominal_mean, _nominal_std = C.NOMINAL[asset_type][f]
        breaches.append({
            "feature": f,
            "level": level,
            "deviation_z": z,
            "direction": "high" if z > 0 else "low",
            "current": current[f],
            "nominal": nominal_mean,
        })
    breaches.sort(key=lambda b: -abs(b["deviation_z"]))

    trend_features = []
    for f, delta in trends.items():
        if abs(delta) >= C.ANOMALY_TREND_Z and abs(deviations[f]) >= 1.0:
            trend_features.append({
                "feature": f,
                "trend_delta_z": delta,
                "direction": "rising" if delta > 0 else "falling",
            })
    trend_features.sort(key=lambda b: -abs(b["trend_delta_z"]))

    max_abs = max((abs(z) for z in deviations.values()), default=0.0)
    if any(b["level"] == "CRITICAL" for b in breaches):
        status = "CRITICAL"
    elif breaches or trend_features:
        status = "WARNING"
    else:
        status = "NORMAL"

    anomaly_score = round(min(100.0, (max_abs / C.ANOMALY_CRITICAL_Z) * 100.0), 1)
    catastrophic_risk = status == "CRITICAL" and criticality >= 4
    if status == "CRITICAL":
        recommendation = "Escalate inspection and verify against SOP condition limits."
    elif status == "WARNING":
        recommendation = "Increase monitoring frequency and verify sensor condition."
    else:
        recommendation = "No independent sensor abnormality detected."

    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "status": status,
        "anomaly_score": anomaly_score,
        "early_warning": status != "NORMAL",
        "catastrophic_risk": catastrophic_risk,
        "current_readings": current,
        "deviations": deviations,
        "trend_delta_z": trends,
        "breached_features": breaches,
        "trend_features": trend_features,
        "top_drivers": [f for f, _z in sorted(deviations.items(), key=lambda kv: -abs(kv[1]))[:3]],
        "thresholds": {
            "warning_z": C.ANOMALY_WARNING_Z,
            "critical_z": C.ANOMALY_CRITICAL_Z,
            "trend_z": C.ANOMALY_TREND_Z,
        },
        "recommendation": recommendation,
    }


# ==========================================================================
# TOOL 3: RAG over manuals / SOPs / incidents (asset-filtered)
# ==========================================================================
def rag_tool(query: str, asset_id: str | None = None, k: int = 4) -> dict:
    hits = _rag().query(query, asset_id=asset_id, k=k)
    return {"query": query, "asset_id": asset_id, "backend": _rag().kind, "results": hits}


# ==========================================================================
# TOOL 4: ERP inventory (stock + lead times + alternatives)
# ==========================================================================
def inventory_tool(asset_id: str) -> dict:
    parts = pd.read_csv(C.PARTS_CSV)
    p = parts[parts.asset_id == asset_id]
    items = []
    for _, r in p.iterrows():
        in_stock = int(r["qty_on_hand"]) > 0
        items.append({
            "part_no": r["part_no"], "description": r["description"],
            "qty_on_hand": int(r["qty_on_hand"]),
            "lead_time_days": int(r["lead_time_days"]),
            "unit_cost_usd": float(r["unit_cost_usd"]),
            "status": "IN STOCK" if in_stock else f"OUT - reorder ({int(r['lead_time_days'])}d lead)",
        })
    items.sort(key=lambda x: (x["qty_on_hand"] > 0, -x["lead_time_days"]))
    return {"asset_id": asset_id, "parts": items}


# ==========================================================================
# TOOL 5: SQL query (transparent - returns the SQL it ran)
# ==========================================================================
def sql_query_tool(sql: str) -> dict:
    """Run read-only SQL against assets/sensors/delays/incidents/parts.

    Accepts a single SELECT or read-only WITH (CTE) statement. Requiring the
    statement to start with SELECT/WITH and forbidding multiple statements is
    sufficient for read-only safety - SQLite has no data-modifying CTEs, so a
    lone SELECT/WITH cannot mutate. (A keyword denylist was avoided because it
    false-rejects valid content queries, e.g. LIKE '%replace%' over incident
    resolutions.) The exact SQL is returned for UI validation."""
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        return {"sql": sql, "error": "Only read-only SELECT / WITH queries are permitted."}
    if ";" in s.rstrip(";"):
        return {"sql": sql, "error": "Multiple statements are not permitted."}
    try:
        rows = _db().run(sql)
        return {"sql": sql, "row_count": len(rows), "rows": rows[:50]}
    except Exception as e:
        return {"sql": sql, "error": str(e)}


# ==========================================================================
# TOOL 6: Delay history (production impact)
# ==========================================================================
def delay_history_tool(asset_id: str) -> dict:
    dl = pd.read_csv(C.DELAY_LOGS_CSV)
    g = dl[dl.asset_id == asset_id]
    if g.empty:
        return {"asset_id": asset_id, "events": 0, "total_downtime_min": 0, "tonnage_lost": 0}
    top = (g.groupby("delay_desc")["downtime_min"].sum()
           .sort_values(ascending=False).head(3).to_dict())
    return {
        "asset_id": asset_id, "events": int(len(g)),
        "total_downtime_min": int(g["downtime_min"].sum()),
        "tonnage_lost": round(float(g["tonnage_lost"].sum()), 1),
        "top_causes": {k: int(v) for k, v in top.items()},
    }


# ==========================================================================
# TOOL 7: Deterministic risk / priority scoring (Step 4)
# ==========================================================================
def _band(score):
    for thr, name in PRIORITY_BANDS:
        if score >= thr:
            return name
    return "LOW"

def learned_bias(asset_id: str) -> tuple[float, int]:
    """Per-asset priority adjustment *learned* from engineer feedback.

    Each feedback record carries a `severity_adjust` in [-25, +25] (the engineer
    saying "this was more/less urgent than you scored it"). We return the mean
    adjustment for the asset and the number of records behind it. With no
    feedback file the bias is 0, so default behaviour - and the eval baseline -
    is unchanged.
    """
    if not os.path.exists(C.FEEDBACK_CSV):
        return 0.0, 0
    try:
        fb = pd.read_csv(C.FEEDBACK_CSV)
    except Exception:
        return 0.0, 0
    if "asset_id" not in fb.columns or "severity_adjust" not in fb.columns:
        return 0.0, 0
    g = fb[fb["asset_id"] == asset_id]
    if g.empty:
        return 0.0, 0
    adj = float(pd.to_numeric(g["severity_adjust"], errors="coerce").fillna(0).mean())
    return max(-25.0, min(25.0, adj)), int(len(g))

def risk_score_tool(asset_id: str) -> dict:
    reg = _registry()
    row = reg[reg.asset_id == asset_id]
    if row.empty:
        return {"error": f"Unknown asset {asset_id}"}
    crit = int(row.iloc[0]["criticality"])

    prog = prognostic_tool(asset_id)
    rul = prog.get("rul_days", MAX_RUL_DAYS)
    delays = delay_history_tool(asset_id)
    inv = inventory_tool(asset_id)

    # normalise sub-scores to 0..1 (1 = most urgent)
    rul_score = max(0.0, 1 - rul / MAX_RUL_DAYS)
    crit_score = crit / 5.0
    downtime = delays["total_downtime_min"]
    delay_score = min(1.0, downtime / 600.0)
    # spares: urgent if a needed part is out AND lead time long
    out_parts = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
    max_lead = max([p["lead_time_days"] for p in out_parts], default=0)
    spares_score = min(1.0, max_lead / 45.0) if out_parts else 0.0

    base_score = 100 * (
        RISK_WEIGHTS["rul"] * rul_score +
        RISK_WEIGHTS["criticality"] * crit_score +
        RISK_WEIGHTS["delay_history"] * delay_score +
        RISK_WEIGHTS["spares"] * spares_score
    )

    # feedback-driven correction: engineers' learned adjustment for this asset.
    # Applied to the headline score ONLY when explicitly enabled (off by
    # default) so priority stays grounded in the stated basis - RUL,
    # criticality, delay history, spares/lead time - and reproducible.
    raw_bias, fb_count = learned_bias(asset_id)
    bias = raw_bias if C.APPLY_FEEDBACK_BIAS else 0.0
    score = round(max(0.0, min(100.0, base_score + bias)), 1)

    # constraint-aware flag: can we fix before it fails?
    parts_gap = max_lead > rul if out_parts else False

    return {
        "asset_id": asset_id,
        "priority_score": score,
        "priority_band": _band(score),
        "base_score": round(base_score, 1),
        "learned_adjustment": round(bias, 1),          # actually applied (0 unless enabled)
        "learned_adjustment_available": round(raw_bias, 1),
        "feedback_bias_applied": C.APPLY_FEEDBACK_BIAS,
        "feedback_count": fb_count,
        "components": {
            "rul_score": round(rul_score, 2), "criticality_score": round(crit_score, 2),
            "delay_score": round(delay_score, 2), "spares_score": round(spares_score, 2),
        },
        "rul_days": rul,
        "criticality": crit,
        "constraint_flag": ("LEAD TIME EXCEEDS RUL - part arrives after predicted "
                            f"failure ({max_lead}d lead vs {rul:.0f}d RUL); "
                            "shift to monitored degradation strategy."
                            if parts_gap else None),
    }


# ==========================================================================
# TOOL 7.5: Plant cascade impact (bottleneck prioritization at plant level)
# ==========================================================================
def cascade_tool(asset_id: str) -> dict:
    """Plant-level impact of this asset failing: which downstream assets idle,
    the criticality-weighted blast radius, and a system_priority that escalates
    own priority by cascade impact. Additive by design - priority_score and
    RISK_WEIGHTS are untouched (eval-baseline safe).
    """
    from agent import cascade
    own_res = risk_score_tool(asset_id)
    if "error" in own_res:
        return {"asset_id": asset_id, "error": own_res["error"]}
    own = own_res["priority_score"]
    blast, path = cascade.blast_radius(asset_id)
    blast_points = round(C.CASCADE_GAIN * blast, 1)
    system_priority = round(min(100.0, own + blast_points), 1)
    return {
        "asset_id": asset_id,
        "own_priority": own,
        "blast_radius": round(blast, 2),
        "blast_points": blast_points,
        "system_priority": system_priority,
        "downstream": path,                      # [{asset_id, name, hops, criticality}]
        "downstream_count": len(path),
        "path_str": " -> ".join([asset_id] + [d["asset_id"] for d in path]),
    }


# ==========================================================================
# TOOL 7.6: Next-shift planner (plant-scope; allocates finite crew-hours)
# ==========================================================================
def shift_plan_tool() -> dict:
    """Propose the next-shift action queue for the whole plant: rank flagged
    assets by system_priority (cascade-aware), allocate finite crew-hours per
    skill, defer what doesn't fit (with reasons), and divert parts-infeasible
    jobs to monitored degradation + procurement. Composes existing verified
    tools - additive; priority_score / RISK_WEIGHTS untouched.
    """
    from agent import planner
    reg = _registry()
    candidates = []
    for aid in reg.asset_id:
        risk = risk_score_tool(aid)
        if "error" in risk:
            continue
        abn = abnormality_tool(aid)
        flagged = (risk["priority_band"] in ("HIGH", "CRITICAL")
                   or bool(risk.get("constraint_flag"))
                   or abn.get("status") != "NORMAL")
        if not flagged:
            continue
        casc = cascade_tool(aid)
        candidates.append({
            "asset_id": aid,
            "asset_type": reg[reg.asset_id == aid].iloc[0]["type"],
            "system_priority": casc.get("system_priority", risk["priority_score"]),
            "rul_days": risk["rul_days"],
            "criticality": risk["criticality"],
            "priority_band": risk["priority_band"],
            "constraint_flag": risk.get("constraint_flag"),
        })
    crew = pd.read_csv(C.CREW_ROSTER_CSV).to_dict("records")
    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    templates = {r["asset_type"]: {"task": r["task"], "est_hours": float(r["est_hours"]),
                                   "required_skill": r["required_skill"]}
                 for _, r in jt.iterrows()}
    plan = planner.plan_shift(candidates, crew, templates)
    plan["candidate_count"] = len(candidates)
    return plan


# ==========================================================================
# TOOL 7.7: CMMS draft work orders (system of action - draft write-back)
# ==========================================================================
def work_order_draft_tool(persist: bool = False, out_dir: str | None = None) -> dict:
    """Draft one trace-backed work order per SCHEDULED next-shift job. Composes
    shift_plan_tool with per-asset evidence (risk, cascade, spares, SOP
    citations, crew + planned hours). Approval-gated: every WO is a DRAFT and is
    never auto-closed. Parts-infeasible / deferred jobs get NO work order - they
    stay procurement / monitored-degradation actions.

    persist=False (default) is side-effect-free; persist=True writes one JSON per
    WO to out_dir (default config.WORK_ORDERS_DIR) - opt-in, like alert dispatch.
    """
    plan = shift_plan_tool()
    reg = _registry()
    name_of = dict(zip(reg.asset_id, reg.name))
    stamp = datetime.now()

    work_orders = []
    for job in plan.get("scheduled", []):
        aid = job["asset_id"]
        risk = risk_score_tool(aid)
        casc = cascade_tool(aid)
        inv = inventory_tool(aid)
        rag = rag_tool(f"isolation repair procedure {job.get('task', '')}", asset_id=aid, k=3)
        sop_citations = [h["source"] for h in rag.get("results", [])
                         if str(h.get("type", "")).lower() == "manual"]
        spares = [{"part_no": p["part_no"], "status": p["status"],
                   "qty_on_hand": p["qty_on_hand"], "lead_time_days": p["lead_time_days"]}
                  for p in inv.get("parts", [])]
        work_orders.append({
            "work_order_id": f"WO-{aid}-{stamp:%Y%m%d_%H%M%S_%f}",
            "status": "DRAFT",
            "asset_id": aid,
            "asset_name": name_of.get(aid, aid),
            "task": job.get("task"),
            "crew_id": job.get("crew_id"),
            "planned_hours": job.get("est_hours"),
            "system_priority": job.get("system_priority"),
            "priority_band": risk.get("priority_band"),
            "rul_days": risk.get("rul_days"),
            "evidence": {
                "risk": {"priority_score": risk.get("priority_score"),
                         "priority_band": risk.get("priority_band"),
                         "constraint_flag": risk.get("constraint_flag"),
                         "components": risk.get("components")},
                "cascade": {"system_priority": casc.get("system_priority"),
                            "blast_radius": casc.get("blast_radius"),
                            "downstream_count": casc.get("downstream_count"),
                            "path_str": casc.get("path_str")},
                "spares": spares,
                "sop_citations": sop_citations,
            },
            "approval": {"required": True, "approved": False,
                         "note": "Draft only - requires engineer approval; no autonomous closure."},
            "generated_at": stamp.isoformat(timespec="microseconds"),
        })

    persisted = []
    if persist:
        target = out_dir or C.WORK_ORDERS_DIR
        os.makedirs(target, exist_ok=True)
        for w in work_orders:
            path = os.path.join(target, f"{w['work_order_id']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(w, f, indent=2)
            persisted.append(path)

    return {"work_orders": work_orders, "count": len(work_orders),
            "persisted": persisted,
            "basis": ("One DRAFT work order per scheduled next-shift job; "
                      "parts-infeasible / deferred jobs get none. Approval-gated; "
                      "no autonomous closure.")}


# ==========================================================================
# TOOL 7.9: cost_tool (asset-scope financial exposure; folds into Blocks 1 & 4)
# ==========================================================================
def _primary_part(asset_id: str, asset_type: str) -> dict | None:
    """Resolve the limiting part for the asset's templated job via job_templates'
    primary_part_no, matched into this asset's own inventory rows by exact part_no.
    Never substitute a different physical part."""
    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    row = jt[jt.asset_type == asset_type]
    if row.empty or "primary_part_no" not in jt.columns:
        return {"unresolved": True, "primary_part_no": None,
                "reason": "no job template primary_part_no"}
    want_raw = row.iloc[0].get("primary_part_no")
    if pd.isna(want_raw) or not str(want_raw).strip():
        return {"unresolved": True, "primary_part_no": None,
                "reason": "blank job template primary_part_no"}
    want = str(want_raw).strip()
    inv = inventory_tool(asset_id).get("parts", [])
    match = next((p for p in inv if p["part_no"] == want), None)
    if match is None:
        return {"unresolved": True, "primary_part_no": want,
                "reason": "primary part not stocked for this asset; mapping unresolved"}
    return {**match, "unresolved": False, "primary_part_no": want}


def cost_tool(asset_id: str) -> dict:
    """Estimated expected event-cost proxy, feasible action, and EMV for one asset.
    All dollar figures derive from tool outputs + config economics (never invented)."""
    from agent import cascade, economics
    reg = _registry()
    row = reg[reg.asset_id == asset_id]
    if row.empty:
        return {"error": f"Unknown asset {asset_id}"}
    atype = row.iloc[0]["type"]

    # per-event proxy (divide aggregate delay history by event count; type default if none)
    dl = delay_history_tool(asset_id)
    events = dl.get("events", 0)
    if events > 0:
        dt_per = dl["total_downtime_min"] / events
        tn_per = dl["tonnage_lost"] / events
    else:
        dt_per = C.DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE.get(atype, 60)
        tn_per = C.DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE.get(atype, 20)

    rate = C.DOWNTIME_COST_USD_PER_HOUR.get(atype)
    if rate is None:
        return {"error": f"No DOWNTIME_COST_USD_PER_HOUR for type {atype}"}

    own = economics.direct_event_cost(
        asset_type=atype, downtime_min_per_event=dt_per, tonnage_lost_per_event=tn_per,
        downtime_cost_usd_per_hour=rate, tonnage_margin_usd_per_ton=C.TONNAGE_MARGIN_USD_PER_TON)

    # cascade-coupled failure cost (composition lives HERE, not in the pure core)
    failure_cost = own["total_usd"]
    for nid, hops in cascade.downstream(asset_id):
        nrow = reg[reg.asset_id == nid]
        if nrow.empty:
            continue
        ntype = nrow.iloc[0]["type"]
        nrate = C.DOWNTIME_COST_USD_PER_HOUR.get(ntype, rate)
        nd = economics.direct_event_cost(
            asset_type=ntype,
            downtime_min_per_event=C.DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE.get(ntype, 60),
            tonnage_lost_per_event=C.DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE.get(ntype, 20),
            downtime_cost_usd_per_hour=nrate,
            tonnage_margin_usd_per_ton=C.TONNAGE_MARGIN_USD_PER_TON)
        failure_cost += nd["total_usd"] * (C.CASCADE_DECAY ** hops)

    prog = prognostic_tool(asset_id)
    p_fail = prog.get("failure_probability_30d", 0.0)
    rul = prog.get("rul_days", C.MAX_RUL_DAYS)

    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    trow = jt[jt.asset_type == atype]
    est_hours = float(trow.iloc[0]["est_hours"]) if not trow.empty else 3.0
    task = str(trow.iloc[0]["task"]) if not trow.empty else "Inspect asset"
    part = _primary_part(asset_id, atype)
    unresolved = bool(part and part.get("unresolved"))
    template_part_no = part.get("primary_part_no") if part else None
    part_no = None if unresolved else (part["part_no"] if part else None)
    part_cost = 0.0 if unresolved or not part else float(part["unit_cost_usd"])
    in_stock = bool(part and not unresolved and part["qty_on_hand"] > 0)
    lead = int(part["lead_time_days"]) if part and not unresolved else None

    # feasibility action (planner-bucket anchoring is applied in risk_simulator_tool)
    if unresolved:
        action, reason = "monitor", "primary part not stocked for this asset; mapping unresolved"
        act_cost = 0.0
    elif in_stock:
        action, reason = "repair_now", "primary part in stock"
        act_cost = economics.planned_action_cost(
            planned_hours=est_hours, downtime_cost_usd_per_hour=rate,
            planned_stop_cost_factor=C.PLANNED_STOP_COST_FACTOR,
            primary_part_unit_cost_usd=part_cost)["total_usd"]
    elif lead is not None and lead < rul:
        action, reason = "procure_for_window", "out of stock; normal lead within RUL"
        act_cost = economics.planned_action_cost(
            planned_hours=est_hours, downtime_cost_usd_per_hour=rate,
            planned_stop_cost_factor=C.PLANNED_STOP_COST_FACTOR,
            primary_part_unit_cost_usd=part_cost)["total_usd"]
    else:
        action, reason = "monitor", "primary part lead time exceeds predicted RUL"
        act_cost = 0.0

    val = economics.emv(p_failure=p_fail, failure_cost_usd=failure_cost, action_cost_usd=act_cost)
    return {
        "asset_id": asset_id,
        "event_cost_proxy": {
            "label": own["label"], "event_count": int(events),
            "downtime_min_per_event": round(dt_per, 1),
            "tonnage_lost_per_event": round(tn_per, 1),
            "total_usd": own["total_usd"],
        },
        "failure_cost_usd": round(failure_cost, 2),
        "primary_part_unresolved": unresolved,
        "planned_job": {"task": task, "primary_part_no": part_no,
                        "template_primary_part_no": template_part_no,
                        "est_hours": est_hours},
        "feasibility": {"action": action, "reason": reason,
                        "lead_time_days": lead, "predicted_rul_days": round(rul, 1),
                        "in_stock": in_stock},
        "emv": val,
    }


# ==========================================================================
# TOOL 7.95: risk_simulator_tool (plant-scope EML distribution + prescription)
# ==========================================================================
def risk_simulator_tool(trials: int | None = None) -> dict:
    """Seeded plant-risk distribution and feasible-action prescription, anchored to
    the next-shift planner's buckets so prescriptions are crew- and parts-feasible."""
    from agent import cascade, risk_simulator
    reg = _registry()
    g = cascade.build_graph()
    nodes = list(g.keys())
    edges = [(u, v, C.CASCADE_DECAY) for u, vs in g.items() for v in vs]

    seed_probs, node_cost, cost_by_asset = {}, {}, {}
    for nid in nodes:
        c = cost_tool(nid)
        if "error" in c:
            continue
        cost_by_asset[nid] = c
        node_cost[nid] = c["event_cost_proxy"]["total_usd"]
        seed_probs[nid] = prognostic_tool(nid).get("failure_probability_30d", 0.0)

    n_trials = int(trials or C.SIMULATION_TRIALS)
    sim = risk_simulator.simulate_plant_risk(
        nodes, edges, seed_probs, node_cost, trials=n_trials, seed=C.SIMULATION_SEED)
    loss_contrib = sim.get("loss_contributions", {})

    # planner buckets -> per-asset bucket label for feasibility anchoring
    plan = shift_plan_tool()
    bucket = {}
    for r in plan.get("scheduled", []):
        bucket[r["asset_id"]] = "scheduled"
    for r in plan.get("procurement", []):
        bucket[r["asset_id"]] = "procurement-monitor"
    for r in plan.get("deferred", []):
        bucket[r["asset_id"]] = "deferred"

    candidates = []
    for nid, c in cost_by_asset.items():
        b = bucket.get(nid)
        if b is None:
            continue                          # not flagged this shift
        feas = c["feasibility"]["action"]
        if b == "deferred":
            action = "defer_capacity"
        elif b == "scheduled" and feas == "repair_now":
            action = "repair_now"
        else:
            action = feas if feas in ("procure_for_window", "monitor") else "monitor"
        planned_action_cost = c["emv"]["action_cost_usd"]
        current_shift_cost = planned_action_cost if action == "repair_now" else 0.0
        candidates.append({
            "asset_id": nid, "planner_bucket": b, "action": action,
            "primary_part_no": c["planned_job"]["primary_part_no"],
            "primary_part_unresolved": c.get("primary_part_unresolved", False),
            "lead_time_days": c["feasibility"]["lead_time_days"],
            "predicted_rul_days": c["feasibility"]["predicted_rul_days"],
            "intervention_cost_usd": current_shift_cost,
            "planned_action_cost_usd": planned_action_cost,
            "value_at_risk_usd": loss_contrib.get(nid, 0.0),
        })

    ranked = risk_simulator.rank_interventions(
        nodes, edges, seed_probs, node_cost, candidates,
        trials=n_trials, seed=C.SIMULATION_SEED)
    return {"simulation": {k: sim[k] for k in
                           ("mean_eml_usd", "p50_eml_usd", "p90_eml_usd",
                            "p95_eml_usd", "trial_count", "seed")},
            "top_contributors": sim["top_contributors"],
            "prescriptions": ranked}


# ==========================================================================
# TOOL 8: Real-time alert dispatch (logs to notifications; mock SMTP)
# ==========================================================================
def _role_for_band(risk_level: str) -> str:
    rl = (risk_level or "").upper()
    if "CRITICAL" in rl:
        return "supervisor"
    if rl == "HIGH":
        return "reliability"
    return "maintenance"


def alert_dispatch_tool(asset_id: str, risk_level: str, summary: str,
                        recipients: str | None = None, role: str | None = None,
                        dry_run: bool = False) -> dict:
    """Dispatch a real-time, role-routed alert (OE-06).

    Recipient resolution: an explicit `recipients` wins; else an explicit `role`
    maps via config.ALERT_ROLES; else the role is auto-selected from the risk
    band (critical -> supervisor, high -> reliability, else maintenance).
    `dry_run` evaluates the alert without writing (diagnosis stays
    side-effect-free); live dispatch is de-duplicated so the same asset+band on
    the same day is not logged twice."""
    if recipients is None:
        role = role or _role_for_band(risk_level)
        recipients = C.ALERT_ROLES.get(role, C.ALERT_ROLES["maintenance"])
    elif role is None:
        role = "explicit"
    now = datetime.now()
    note = {
        "ts": now.strftime("%Y-%m-%d %H:%M"),
        "asset_id": asset_id, "risk_level": risk_level, "role": role,
        "summary": summary, "recipients": recipients,
    }
    if dry_run:
        return {"dispatched": False, "dry_run": True, **note}

    path = os.path.join(C.DATA_DIR, "notifications.jsonl")
    today = now.strftime("%Y-%m-%d")
    if os.path.exists(path):  # de-dup: one alert per asset+band+day
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if (e.get("asset_id") == asset_id and e.get("risk_level") == risk_level
                        and str(e.get("ts", "")).startswith(today)):
                    return {"dispatched": False, "deduped": True, **note}
    with open(path, "a") as f:
        f.write(json.dumps(note) + "\n")
    return {"dispatched": True, **note}


# ==========================================================================
# TOOL 9: Task closure compliance checklist (System of Action loop closure)
# ==========================================================================
CLOSURE_ITEMS = ["parts_recorded", "steps_logged", "isolation_cleared",
                 "follow_up_scheduled", "digital_logbook_entry"]

def task_closure_tool(work_order_id: str, checklist: dict | None = None) -> dict:
    checklist = checklist or {}
    state = {item: bool(checklist.get(item, False)) for item in CLOSURE_ITEMS}
    missing = [k for k, v in state.items() if not v]
    return {
        "work_order_id": work_order_id,
        "checklist": state,
        "completion_blocked_by": missing,
        "can_close": len(missing) == 0,
        "message": ("Job may be closed - all compliance items satisfied."
                    if not missing else
                    f"Closure BLOCKED. Outstanding: {', '.join(missing)}."),
    }


# --------------------------------------------------------------------------
# Logbook persistence (used by the UI and the feedback loop)
# --------------------------------------------------------------------------
def append_logbook(entry: dict):
    path = C.LOGBOOK_CSV
    df = pd.DataFrame([entry])
    if os.path.exists(path):
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, index=False)


# --------------------------------------------------------------------------
# Feedback loop (FuncReq 6): engineer corrections/outcomes improve future runs
# --------------------------------------------------------------------------
def record_feedback(asset_id: str, work_order_id: str = "", note: str = "",
                    correction: str = "", severity_adjust: float = 0.0,
                    outcome: str = "", reindex: bool = True) -> dict:
    """Persist an engineer correction/confirmation/outcome and learn from it.

    Two learning channels, both immediate:
      1. Retrieval: the feedback text is re-indexed into the RAG corpus (see
         knowledge/rag.build_chunks), so the next diagnosis of this asset
         surfaces the engineer's own words.
      2. Prioritisation: `severity_adjust` (-25..+25) is stored as advisory
         calibration. It shifts the headline priority score only when the
         explicit MW_APPLY_FEEDBACK_BIAS opt-in is enabled.
    """
    global _RAG
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "asset_id": asset_id, "work_order_id": work_order_id,
        "note": note, "correction": correction,
        "severity_adjust": float(severity_adjust), "outcome": outcome,
    }
    df = pd.DataFrame([row])
    if os.path.exists(C.FEEDBACK_CSV):
        df.to_csv(C.FEEDBACK_CSV, mode="a", header=False, index=False)
    else:
        df.to_csv(C.FEEDBACK_CSV, index=False)

    reindexed = False
    if reindex:
        try:  # rebuild the index so the correction is retrievable immediately
            from knowledge.rag import build_index
            build_index()
            _RAG = None  # force tools to reload the refreshed index
            reindexed = True
        except Exception:
            pass

    bias, fb_count = learned_bias(asset_id)
    return {
        "recorded": True, "asset_id": asset_id, "feedback_count": fb_count,
        "learned_adjustment": round(bias, 1), "reindexed": reindexed,
        "message": (f"Feedback stored for {asset_id}. The system has now learned "
                    f"from {fb_count} record(s) on this asset "
                    f"(priority Δ {bias:+.1f})."),
    }


if __name__ == "__main__":
    print("resolve:", resolve_asset("that valve that keeps leaking"))
    print("prognostic:", json.dumps(prognostic_tool("CONV-BELT-03"), indent=2)[:300])
    print("abnormality:", json.dumps(abnormality_tool("CONV-BELT-03"), indent=2)[:300])
    print("risk:", json.dumps(risk_score_tool("HYD-VALVE-07"), indent=2))
