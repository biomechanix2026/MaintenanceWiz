"""Slim serverless core for the hosted Maintenance Wizard demo (Gemini).

Differences from the full local build (agent/orchestrator.py + agent/tools.py):
- LLM is Gemini 2.5 Flash via the free AI Studio key (GEMINI_API_KEY), not
  Claude - the public demo must cost nothing to run.
- prognostic/abnormality/risk serve a precomputed snapshot
  (web/data/snapshot.json) exported by scripts/build_demo_assets.py.
- Retrieval is BM25-only over the exported chunk file; BM25Index is copied
  verbatim from knowledge/rag.py (pure stdlib - no extra dependency).
- fault_mode_tool and feedback_tool are not deployed; alert_dispatch_tool is
  forced dry-run (no side effects on a stateless instance).
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

from google import genai
from google.genai import types

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_BOM = chr(0xFEFF)  # platform env tooling (e.g. PowerShell pipes) prepends this


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip().lstrip(_BOM) or default


MODEL = _env("WIZARD_MODEL", "gemini-2.5-flash")
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
    return _load("tools", lambda: types.Tool(function_declarations=[
        types.FunctionDeclaration(**t) for t in json.loads(
            (DATA_DIR / "tools.json").read_text(encoding="utf-8"))]))


def _system_prompt() -> str:
    return _load("system", lambda:
                 (DATA_DIR / "system_prompt.txt").read_text(encoding="utf-8"))


def chat_turn(message: str, history: list[dict]) -> tuple[dict, list[dict]]:
    """One stateless turn. Returns (rendered, updated_history)."""
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
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.models.generate_content(
            model=MODEL, contents=contents, config=config_)
        candidate = response.candidates[0]
        contents.append(candidate.content)
        calls = [p.function_call for p in (candidate.content.parts or [])
                 if p.function_call]
        if not calls:
            text = "".join(p.text for p in (candidate.content.parts or [])
                           if p.text)
            rendered = {"text": text, "sources": sources,
                        "stop_reason": str(candidate.finish_reason)}
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
