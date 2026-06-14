"""Slim serverless core for the hosted Maintenance Wizard demo (Gemini).

Differences from the full local build (agent/orchestrator.py + agent/tools.py):
- LLM is Gemini 2.5 Flash via the free AI Studio key (GEMINI_API_KEY), not
  Claude - the public demo must cost nothing to run.
- prognostic/abnormality/risk serve a precomputed snapshot
  (web/data/snapshot.json) exported by scripts/build_demo_assets.py.
- Retrieval is BM25-only over the exported chunk file; BM25Index is copied
  verbatim from knowledge/rag.py (pure stdlib - no extra dependency).
- fault_mode_tool, feedback_tool, cascade_tool, shift_plan_tool and
  work_order_draft_tool are not deployed (config/model/scan/write dependencies
  the slim build doesn't bundle); alert_dispatch_tool is forced dry-run (no side
  effects on a stateless instance).
- SQLite is opened read-only on the bundled file (no writes are needed).
- Stateless: the client sends full message history each request and gets the
  updated history back (google-genai Content dicts).
"""
from __future__ import annotations
import difflib
import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

try:
    from google import genai
    from google.genai import errors, types
except ModuleNotFoundError:  # pure dashboard/tests can run without google-genai
    genai = None
    errors = None
    types = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_BOM = chr(0xFEFF)  # platform env tooling (e.g. PowerShell pipes) prepends this


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip().lstrip(_BOM) or default


MODEL = _env("WIZARD_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = _env("WIZARD_FALLBACK_MODEL", "gemini-2.5-flash-lite")
MAX_TOKENS = int(_env("WIZARD_MAX_TOKENS", "4000"))
MAX_TOOL_ROUNDS = 10
RATE_LIMIT = 20      # requests per IP ...
RATE_WINDOW = 3600   # ... per hour (in-memory, per warm instance)

# Role routing copied from config.ALERT_ROLES (the demo bundles no config.py)
ALERT_ROLES = {
    "maintenance": "maintenance-team@plant.local",
    "reliability": "reliability-engineering@plant.local",
    "supervisor":  "shift-supervisor@plant.local",
}

SIGNATURE_ASSET_ID = "GEARBOX-05"

_cache: dict = {}
_hits: dict[str, list[float]] = {}


def _load(name, loader):
    if name not in _cache:
        _cache[name] = loader()
    return _cache[name]


def _chunks() -> list[dict]:
    return _load("chunks", lambda: [
        json.loads(line) for line in
        (DATA_DIR / "bm25_chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()])


def _snapshot() -> dict:
    return _load("snapshot", lambda: json.loads(
        (DATA_DIR / "snapshot.json").read_text(encoding="utf-8")))


def _aliases() -> dict:
    return _load("aliases", lambda: json.loads(
        (DATA_DIR / "aliases.json").read_text(encoding="utf-8")))


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DATA_DIR / 'maintenance.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _all_assets() -> list[dict]:
    with closing(_db()) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT asset_id, name, type, line, criticality FROM assets "
            "ORDER BY asset_id").fetchall()]


def _rows(table: str, asset_id: str) -> list[dict]:
    with closing(_db()) as conn:
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM {table} WHERE asset_id = ?", (asset_id,)).fetchall()]


def _delay_summary(asset_id: str) -> dict:
    return delay_history_tool(asset_id)


def _incident_summary(asset_id: str, limit: int = 3) -> list[dict]:
    with closing(_db()) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM incidents WHERE asset_id = ? ORDER BY date DESC LIMIT ?",
            (asset_id, limit)).fetchall()]


def _evidence_hits(asset_id: str, query: str = "isolation repair procedure") -> list[dict]:
    return rag_tool(query, asset_id=asset_id, k=4).get("results", [])


def _dashboard_asset(row: dict) -> dict:
    aid = row["asset_id"]
    prog = prognostic_tool(aid)
    abn = abnormality_tool(aid)
    risk = risk_score_tool(aid)
    return {
        **row,
        "prognostic": prog,
        "abnormality": abn,
        "risk": risk,
        "inventory": inventory_tool(aid),
        "delay_summary": _delay_summary(aid),
        "incidents": _incident_summary(aid),
        "evidence": _evidence_hits(aid),
    }


def dashboard_payload() -> dict:
    """Read-only dashboard payload for the hosted command-center clone."""
    assets = [_dashboard_asset(row) for row in _all_assets()]
    assets.sort(key=lambda a: (
        -float(a.get("risk", {}).get("priority_score", 0) or 0),
        a.get("asset_id", ""),
    ))
    critical = [a for a in assets if a.get("risk", {}).get("priority_band") == "CRITICAL"]
    abnormal = [a for a in assets if a.get("abnormality", {}).get("status") != "NORMAL"]
    constrained = [a for a in assets if a.get("risk", {}).get("constraint_flag")]
    attention = [
        a for a in assets
        if a.get("risk", {}).get("priority_band") in ("CRITICAL", "HIGH")
        or a.get("abnormality", {}).get("status") != "NORMAL"
        or a.get("risk", {}).get("constraint_flag")
    ]
    signature = next((a for a in assets if a["asset_id"] == SIGNATURE_ASSET_ID), assets[0] if assets else {})
    scenarios = [
        {
            "id": "constraint-flip",
            "title": "The part that cannot arrive in time",
            "asset_id": SIGNATURE_ASSET_ID,
            "prompt": "What's wrong with the mill gearbox?",
            "why": "Lead time exceeds RUL, so the recommendation flips to monitored degradation.",
        },
        {
            "id": "fuzzy-valve",
            "title": "Plant jargon resolution",
            "asset_id": "HYD-VALVE-07",
            "prompt": "That valve that keeps leaking on the caster",
            "why": "Alias resolution happens before tool calls.",
        },
        {
            "id": "offline-eaf",
            "title": "Offline-capable answer",
            "asset_id": "FURNACE-01",
            "prompt": "Check the EAF",
            "why": "The same data contracts work in deterministic mode.",
        },
    ]
    return {
        "generated": _snapshot().get("generated"),
        "asset_count": len(assets),
        "assets": assets,
        "kpis": {
            "critical": len(critical),
            "high": sum(1 for a in assets if a.get("risk", {}).get("priority_band") == "HIGH"),
            "abnormal": len(abnormal),
            "constraint_flagged": len(constrained),
            "value_at_risk_usd": round(sum(
                float(a.get("risk", {}).get("averted_usd", 0) or 0) for a in assets), 2),
        },
        "pre_shift": {
            "needs_attention": len(attention),
            "critical": len(critical),
            "abnormal": len(abnormal),
            "constraint_flagged": len(constrained),
            "assets": [
                {
                    "asset_id": a["asset_id"],
                    "name": a.get("name"),
                    "priority_band": a.get("risk", {}).get("priority_band"),
                    "priority_score": a.get("risk", {}).get("priority_score"),
                    "rul_days": a.get("risk", {}).get("rul_days"),
                    "anomaly_status": a.get("abnormality", {}).get("status"),
                    "constraint_flag": a.get("risk", {}).get("constraint_flag"),
                    "value_at_risk_usd": a.get("risk", {}).get("averted_usd", 0),
                }
                for a in attention[:8]
            ],
        },
        "signature_story": {
            "asset_id": signature.get("asset_id"),
            "risk": signature.get("risk"),
            "prognostic": signature.get("prognostic"),
            "abnormality": signature.get("abnormality"),
            "inventory": signature.get("inventory"),
            "evidence": signature.get("evidence"),
        },
        "scenarios": scenarios,
        "mode_note": "Hosted demo dashboard is deterministic and read-only; chat may use Gemini.",
    }


def rate_limited(ip: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    window = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(window) >= RATE_LIMIT:
        _hits[ip] = window
        return True
    window.append(now)
    _hits[ip] = window
    return False


# --- BM25 (copied verbatim from knowledge/rag.py BM25Index) ------------------

def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25Index:
    K1, B = 1.5, 0.75

    def __init__(self, chunks):
        self.chunks = chunks
        self.docs = [_tok(c["text"] + " " + c["source"]) for c in chunks]
        self.doc_len = [len(d) or 1 for d in self.docs]
        self.avg_len = (sum(self.doc_len) / len(self.docs)) if self.docs else 1.0
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def query(self, text, asset_id=None, k=4):
        q = _tok(text)
        scored = []
        for i, c in enumerate(self.chunks):
            if asset_id and c["asset_id"] != asset_id:
                continue
            dl = self.doc_len[i]
            s = 0.0
            for t in q:
                f = self.tf[i].get(t)
                if not f:
                    continue
                s += (self.idf.get(t, 0.0) * f * (self.K1 + 1)
                      / (f + self.K1 * (1 - self.B + self.B * dl / self.avg_len)))
            if s > 0:
                scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        return [{**{kk: c[kk] for kk in ("asset_id", "source", "type", "text")},
                 "score": round(float(s), 4)} for s, c in scored[:k]]


def _bm25() -> BM25Index:
    return _load("bm25", lambda: BM25Index(_chunks()))


# --- tools (same names + result shapes as agent/tools.py) -------------------

def resolve_asset(query: str) -> dict:
    aliases = _aliases()
    with closing(_db()) as conn:
        rows = conn.execute("SELECT asset_id, name FROM assets").fetchall()
    q = query.lower().strip()
    for r in rows:
        if r["asset_id"].lower() in q:
            return {"asset_id": r["asset_id"], "confidence": 1.0,
                    "matched_on": "explicit id"}
    for alias, aid in aliases.items():
        if alias in q:
            return {"asset_id": aid, "confidence": 0.95,
                    "matched_on": f"alias '{alias}'"}
    best = difflib.get_close_matches(q, list(aliases.keys()), n=1, cutoff=0.6)
    if best:
        return {"asset_id": aliases[best[0]], "confidence": 0.75,
                "matched_on": f"fuzzy alias '{best[0]}'"}
    names = {r["name"].lower(): r["asset_id"] for r in rows}
    best = difflib.get_close_matches(q, list(names), n=1, cutoff=0.5)
    if best:
        return {"asset_id": names[best[0]], "confidence": 0.6,
                "matched_on": f"fuzzy name '{best[0]}'"}
    return {"asset_id": None, "confidence": 0.0, "matched_on": None,
            "clarification_needed": True,
            "candidates": [dict(r) for r in rows[:6]]}


def _snap_entry(asset_id: str, key: str) -> dict:
    entry = _snapshot()["assets"].get(asset_id)
    if entry is None:
        known = ", ".join(sorted(_snapshot()["assets"]))
        return {"error": f"No snapshot for {asset_id}. Known assets: {known}"}
    return entry[key]


def prognostic_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "prognostic")


def abnormality_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "abnormality")


def risk_score_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "risk")


def rag_tool(query: str, asset_id: str | None = None, k: int = 4) -> dict:
    hits = _bm25().query(query, asset_id=asset_id, k=k)
    return {"query": query, "asset_id": asset_id,
            "backend": "bm25 (hosted demo)", "results": hits}


def inventory_tool(asset_id: str) -> dict:
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT part_no, description, qty_on_hand, lead_time_days, "
            "unit_cost_usd FROM parts WHERE asset_id = ? "
            "ORDER BY (qty_on_hand > 0) ASC, lead_time_days DESC",
            (asset_id,)).fetchall()
    items = [{"part_no": r["part_no"], "description": r["description"],
              "qty_on_hand": int(r["qty_on_hand"]),
              "lead_time_days": int(r["lead_time_days"]),
              "unit_cost_usd": float(r["unit_cost_usd"]),
              "status": ("IN STOCK" if int(r["qty_on_hand"]) > 0 else
                         f"OUT - reorder ({int(r['lead_time_days'])}d lead)")}
             for r in rows]
    return {"asset_id": asset_id, "parts": items}


def delay_history_tool(asset_id: str) -> dict:
    with closing(_db()) as conn:
        agg = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(downtime_min),0) AS mins, "
            "COALESCE(SUM(tonnage_lost),0) AS tons FROM delays "
            "WHERE asset_id = ?", (asset_id,)).fetchone()
        top = conn.execute(
            "SELECT delay_desc, SUM(downtime_min) AS mins FROM delays "
            "WHERE asset_id = ? GROUP BY delay_desc ORDER BY mins DESC LIMIT 3",
            (asset_id,)).fetchall()
    if agg["n"] == 0:
        return {"asset_id": asset_id, "events": 0,
                "total_downtime_min": 0, "tonnage_lost": 0}
    return {"asset_id": asset_id, "events": int(agg["n"]),
            "total_downtime_min": int(agg["mins"]),
            "tonnage_lost": round(float(agg["tons"]), 1),
            "top_causes": {r["delay_desc"]: int(r["mins"]) for r in top}}


def sql_query_tool(sql: str) -> dict:
    """Same read-only guard as agent/tools.py: a single SELECT/WITH statement."""
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        return {"sql": sql, "error": "Only read-only SELECT / WITH queries are permitted."}
    if ";" in s.rstrip(";"):
        return {"sql": sql, "error": "Multiple statements are not permitted."}
    try:
        with closing(_db()) as conn:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchmany(2000)]
        return {"sql": sql, "row_count": len(rows), "rows": rows[:50]}
    except Exception as e:
        return {"sql": sql, "error": str(e)}


def _role_for_band(risk_level: str) -> str:
    rl = (risk_level or "").upper()
    if "CRITICAL" in rl:
        return "supervisor"
    if rl == "HIGH":
        return "reliability"
    return "maintenance"


def alert_dispatch_tool(asset_id: str, risk_level: str, summary: str,
                        recipients: str | None = None,
                        role: str | None = None) -> dict:
    """Demo build: ALWAYS dry-run. Routing logic mirrors agent/tools.py."""
    if recipients is None:
        role = role or _role_for_band(risk_level)
        recipients = ALERT_ROLES.get(role, ALERT_ROLES["maintenance"])
    elif role is None:
        role = "explicit"
    return {"dispatched": False, "dry_run": True,
            "note": "live dispatch disabled in the hosted demo",
            "asset_id": asset_id, "risk_level": risk_level, "role": role,
            "summary": summary, "recipients": recipients}


CLOSURE_ITEMS = ["parts_recorded", "steps_logged", "isolation_cleared",
                 "follow_up_scheduled", "digital_logbook_entry"]


def task_closure_tool(work_order_id: str, checklist: dict | None = None) -> dict:
    checklist = checklist or {}
    state = {item: bool(checklist.get(item, False)) for item in CLOSURE_ITEMS}
    missing = [k for k, v in state.items() if not v]
    return {"work_order_id": work_order_id, "checklist": state,
            "completion_blocked_by": missing, "can_close": len(missing) == 0,
            "message": ("Job may be closed - all compliance items satisfied."
                        if not missing else
                        f"Closure BLOCKED. Outstanding: {', '.join(missing)}.")}


def should_use_gearbox_fallback(message: str, history: list[dict] | None) -> bool:
    """Fresh-turn-only fallback trigger for the signature demo path.

    Uses the same asset resolver as the agent instead of brittle prompt strings,
    and refuses multi-turn fallback so canned content never corrupts a Gemini
    tool-call history.
    """
    if history:
        return False
    resolved = resolve_asset(message or "")
    return resolved.get("asset_id") == SIGNATURE_ASSET_ID


def gearbox_fallback_response(message: str) -> dict:
    """Deterministic five-block response for the hosted signature demo."""
    aid = SIGNATURE_ASSET_ID
    prog = prognostic_tool(aid)
    abn = abnormality_tool(aid)
    risk = risk_score_tool(aid)
    inv = inventory_tool(aid)
    delays = delay_history_tool(aid)
    hits = rag_tool("isolation repair procedure pinion vibration gearbox", asset_id=aid, k=4)["results"]
    parts = inv.get("parts", [])
    out_parts = [p for p in parts if int(p.get("qty_on_hand", 0)) <= 0]
    limiting = max(out_parts or parts, key=lambda p: int(p.get("lead_time_days", 0)), default={})
    shap = prog.get("shap", {})
    drivers = ", ".join(shap.get("ranked_drivers", [])[:3]) or shap.get("top_driver", "sensor deviation")
    source_lines = "\n".join(f"- {h['source']}" for h in hits[:3]) or "- No hosted source matched."
    part_lines = "\n".join(
        f"- `{p['part_no']}`: {p['status']} (lead {p['lead_time_days']}d, unit ${p['unit_cost_usd']:,.0f})"
        for p in parts
    ) or "- No parts mapped."
    constraint = risk.get("constraint_flag") or "No constraint flag in snapshot."
    emv = float(risk.get("emv", 0) or 0)
    value_at_risk = float(risk.get("averted_usd", 0) or 0)
    text = f"""> (Hosted demo fallback: Gemini was unavailable, so this answer is rendered from bundled tool outputs for the signature scenario.)

### 1. Operational Risk Assessment
- **Asset:** `{aid}` | **Priority:** **{risk.get('priority_band')}** (score **{risk.get('priority_score')}/100**)
- **Remaining Useful Life:** **{prog.get('rul_days')} days** | 30-day failure probability: **{float(prog.get('failure_probability_30d', 0)):.0%}**
- **Independent abnormality detector:** **{abn.get('status')}** (score **{abn.get('anomaly_score')}/100**)
- **Delay severity:** {delays.get('events', 0)} events, {delays.get('total_downtime_min', 0)} min downtime, {delays.get('tonnage_lost', 0):.0f} t lost
- **Financial exposure:** ~${value_at_risk:,.0f} value at risk; positive expected value preserved by immediate action: ~${emv:,.0f}

### 2. Diagnostic & Root-Cause Breakdown
- **Top drivers:** {drivers}
- **Abnormal evidence:** {abn.get('recommendation', 'Review sensor deviations.')}
- **Top sensor:** {shap.get('top_driver', 'n/a')} from snapshot attribution method `{shap.get('method', 'snapshot')}`.

### 3. Actionable Maintenance Blueprint
- **Immediate action:** do not assume a normal replacement window; run monitored degradation controls and verify gearbox isolation steps from retrieved SOP evidence.
- **Constraint-aware flip:** the plan changes from simple "replace now" to monitored degradation plus expedited procurement because the limiting part cannot arrive before predicted failure.

### 4. Supply-Chain Logistics Strategy
- **Constraint:** {constraint}
- **Limiting part:** `{limiting.get('part_no', 'n/a')}` with lead time **{limiting.get('lead_time_days', 'n/a')}d** versus RUL **{prog.get('rul_days')}d**.
{part_lines}

### 5. Traceability & Audit Trail
- **Source of truth:** hosted snapshot exported from the real tool suite; no live write was performed.
- **Retrieved sources:**
{source_lines}
- **Fallback trigger:** asset resolver mapped the prompt to `{aid}`; canned fallback is allowed only on a fresh single-turn hosted demo request.
"""
    return {
        "text": text,
        "sources": [{"source": h["source"], "type": h["type"], "asset_id": h["asset_id"]} for h in hits],
        "stop_reason": "hosted_demo_fallback",
        "fallback": True,
        "fallback_note": "Hosted demo fallback: Gemini failed for the signature GEARBOX-05 scenario; rendered from bundled tool outputs.",
        "model": "deterministic-hosted-fallback",
    }


TOOL_FUNCS = {
    "resolve_asset": lambda a: resolve_asset(a["query"]),
    "prognostic_tool": lambda a: prognostic_tool(a["asset_id"]),
    "abnormality_tool": lambda a: abnormality_tool(a["asset_id"]),
    "rag_tool": lambda a: rag_tool(a["query"], a.get("asset_id"), a.get("k", 4)),
    "inventory_tool": lambda a: inventory_tool(a["asset_id"]),
    "sql_query_tool": lambda a: sql_query_tool(a["sql"]),
    "delay_history_tool": lambda a: delay_history_tool(a["asset_id"]),
    "risk_score_tool": lambda a: risk_score_tool(a["asset_id"]),
    "alert_dispatch_tool": lambda a: alert_dispatch_tool(
        a["asset_id"], a["risk_level"], a["summary"],
        a.get("recipients"), a.get("role")),
    "task_closure_tool": lambda a: task_closure_tool(
        a["work_order_id"], a.get("checklist")),
}


def dispatch(name: str, args: dict) -> tuple[object, list[dict] | None]:
    """Run one tool. Returns (result, sources) - sources only for rag_tool."""
    func = TOOL_FUNCS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}, None
    try:
        result = func(dict(args or {}))
    except Exception as exc:  # surface to the model, never crash the loop
        return {"error": f"{type(exc).__name__}: {exc}"}, None
    if name == "rag_tool":
        sources = [{"source": h["source"], "type": h["type"],
                    "asset_id": h["asset_id"]} for h in result["results"]]
        return result, sources
    return result, None


# --- stateless wizard loop ---------------------------------------------------

def _tool_config() -> types.Tool:
    if types is None:
        raise RuntimeError("google-genai is required for hosted chat turns")
    return _load("tools", lambda: types.Tool(function_declarations=[
        types.FunctionDeclaration(**t) for t in json.loads(
            (DATA_DIR / "tools.json").read_text(encoding="utf-8"))]))


def _system_prompt() -> str:
    return _load("system", lambda:
                 (DATA_DIR / "system_prompt.txt").read_text(encoding="utf-8"))


def chat_turn(message: str, history: list[dict]) -> tuple[dict, list[dict]]:
    """One stateless turn. Returns (rendered, updated_history)."""
    if genai is None or types is None or errors is None:
        if should_use_gearbox_fallback(message, history):
            return gearbox_fallback_response(message), []
        raise RuntimeError("google-genai is required for hosted chat turns")

    # A dirty key ends up in an HTTP header and crashes ascii encoding.
    client = genai.Client(api_key=_env("GEMINI_API_KEY") or None)
    contents = [types.Content(**c) for c in history]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    config_ = types.GenerateContentConfig(
        system_instruction=_system_prompt(),
        tools=[_tool_config()],
        max_output_tokens=MAX_TOKENS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
    )
    sources: list[dict] = []
    rendered = {"text": "(stopped: tool-round limit reached)",
                "sources": [], "stop_reason": "tool_round_limit"}
    model = MODEL
    for _ in range(MAX_TOOL_ROUNDS):
        # Free-tier flash 503s under load spikes and 429s at 5 req/min/model
        # (one agentic turn is 3-6 requests). Quota is per model, so after one
        # retry we degrade to the lite model for the remainder of this turn.
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config_)
        except errors.APIError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2)
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=config_)
            except errors.APIError as e2:
                if (e2.code not in (429, 500, 502, 503, 504)
                        or model == FALLBACK_MODEL):
                    if should_use_gearbox_fallback(message, history):
                        return gearbox_fallback_response(message), []
                    raise
                model = FALLBACK_MODEL
                try:
                    response = client.models.generate_content(
                        model=model, contents=contents, config=config_)
                except errors.APIError as e3:
                    if should_use_gearbox_fallback(message, history):
                        return gearbox_fallback_response(message), []
                    raise e3
        candidate = response.candidates[0]
        contents.append(candidate.content)
        calls = [p.function_call for p in (candidate.content.parts or [])
                 if p.function_call]
        if not calls:
            text = "".join(p.text for p in (candidate.content.parts or [])
                           if p.text)
            rendered = {"text": text, "sources": sources,
                        "stop_reason": str(candidate.finish_reason),
                        "model": model}
            break
        parts = []
        for fc in calls:
            result, hit_sources = dispatch(fc.name, dict(fc.args or {}))
            sources.extend(hit_sources or [])
            parts.append(types.Part.from_function_response(
                name=fc.name, response={"result": result}))
        # role="user" is the documented google-genai pattern for returning
        # function responses (verified against the function-calling docs)
        contents.append(types.Content(role="user", parts=parts))
    history_out = [c.model_dump(exclude_none=True, mode="json")
                   for c in contents]
    return rendered, history_out
