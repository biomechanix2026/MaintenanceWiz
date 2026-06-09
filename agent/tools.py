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

    def run(self, sql):
        cur = self.conn.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

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
    return {
        "asset_id": asset_id,
        "asset_type": atype,
        "latest_readings": readings,
        "rul_days": round(rul, 1),
        "failure_probability_30d": round(prob, 3),
        "shap": explain,
    }


# ==========================================================================
# TOOL 2: RAG over manuals / SOPs / incidents (asset-filtered)
# ==========================================================================
def rag_tool(query: str, asset_id: str | None = None, k: int = 4) -> dict:
    hits = _rag().query(query, asset_id=asset_id, k=k)
    return {"query": query, "asset_id": asset_id, "backend": _rag().kind, "results": hits}


# ==========================================================================
# TOOL 3: ERP inventory (stock + lead times + alternatives)
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
# TOOL 4: SQL query (transparent - returns the SQL it ran)
# ==========================================================================
def sql_query_tool(sql: str) -> dict:
    """Run read-only SQL against assets/sensors/delays/incidents/parts."""
    if not sql.strip().lower().startswith("select"):
        return {"sql": sql, "error": "Only SELECT queries are permitted."}
    try:
        rows = _db().run(sql)
        return {"sql": sql, "row_count": len(rows), "rows": rows[:50]}
    except Exception as e:
        return {"sql": sql, "error": str(e)}


# ==========================================================================
# TOOL 5: Delay history (production impact)
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
# TOOL 6: Deterministic risk / priority scoring (Step 4)
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
    g = fb[fb.get("asset_id") == asset_id]
    if g.empty or "severity_adjust" not in g:
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

    # feedback-driven correction: nudge the score by what engineers have learned
    # us about this asset (0 when there is no feedback -> baseline unchanged).
    bias, fb_count = learned_bias(asset_id)
    score = round(max(0.0, min(100.0, base_score + bias)), 1)

    # constraint-aware flag: can we fix before it fails?
    parts_gap = max_lead > rul if out_parts else False

    return {
        "asset_id": asset_id,
        "priority_score": score,
        "priority_band": _band(score),
        "base_score": round(base_score, 1),
        "learned_adjustment": round(bias, 1),
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
# TOOL 7: Real-time alert dispatch (logs to notifications; mock SMTP)
# ==========================================================================
def alert_dispatch_tool(asset_id: str, risk_level: str, summary: str,
                        recipients: str = "maintenance-team@plant.local") -> dict:
    note = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "asset_id": asset_id, "risk_level": risk_level,
        "summary": summary, "recipients": recipients,
    }
    path = os.path.join(C.DATA_DIR, "notifications.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(note) + "\n")
    return {"dispatched": True, **note}


# ==========================================================================
# TOOL 8: Task closure compliance checklist (System of Action loop closure)
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
      2. Prioritisation: `severity_adjust` (-25..+25) shifts this asset's future
         priority score via learned_bias(), so "you under/over-scored this"
         is reflected next time.
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
    print("risk:", json.dumps(risk_score_tool("HYD-VALVE-07"), indent=2))
