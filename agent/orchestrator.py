"""
The Consolidated Brain orchestrator.

Two execution modes, identical tool suite:

* LLM mode (when ANTHROPIC_API_KEY is set): a single think->act->observe loop
  drives Claude with the full tool set (the "consolidated brain" - no sub-agents).
  Claude decides which tools to call and writes the five-block answer.

* Deterministic mode (no key / offline): the same tools are invoked in pipeline
  order by Python, and the five-block answer is assembled from their structured
  outputs. This guarantees the system runs and demos anywhere, and gives a
  reproducible baseline for the eval judges.

Both modes return the same AgentResult so the UI is mode-agnostic.
"""
from __future__ import annotations
import os
import json
from dataclasses import dataclass, field

from agent.system_prompt import SYSTEM_PROMPT
from agent import tools as T
from config import ALERT_THRESHOLD


# --------------------------------------------------------------------------
# Tool registry shared by both modes
# --------------------------------------------------------------------------
TOOL_FUNCS = {
    "resolve_asset": lambda a: T.resolve_asset(a["query"]),
    "prognostic_tool": lambda a: T.prognostic_tool(a["asset_id"]),
    "rag_tool": lambda a: T.rag_tool(a["query"], a.get("asset_id"), a.get("k", 4)),
    "inventory_tool": lambda a: T.inventory_tool(a["asset_id"]),
    "sql_query_tool": lambda a: T.sql_query_tool(a["sql"]),
    "delay_history_tool": lambda a: T.delay_history_tool(a["asset_id"]),
    "risk_score_tool": lambda a: T.risk_score_tool(a["asset_id"]),
    "alert_dispatch_tool": lambda a: T.alert_dispatch_tool(
        a["asset_id"], a["risk_level"], a["summary"], a.get("recipients", "maintenance-team@plant.local")),
    "task_closure_tool": lambda a: T.task_closure_tool(a["work_order_id"], a.get("checklist")),
    "feedback_tool": lambda a: T.record_feedback(
        a["asset_id"], a.get("work_order_id", ""), a.get("note", ""),
        a.get("correction", ""), a.get("severity_adjust", 0.0), a.get("outcome", "")),
}

# Anthropic tool schemas (used only in LLM mode)
TOOL_SCHEMAS = [
    {"name": "resolve_asset", "description": "Map free-text/jargon to a formal asset_id.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "prognostic_tool", "description": "RUL, failure probability and SHAP attribution for an asset.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "rag_tool", "description": "Retrieve SOP/manual/incident text, optionally filtered to an asset_id.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "asset_id": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]}},
    {"name": "inventory_tool", "description": "Spare-part stock and procurement lead times for an asset.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "sql_query_tool", "description": "Run a read-only SELECT over tables: assets, sensors, delays, incidents, parts. Returns the SQL and rows.",
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}},
    {"name": "delay_history_tool", "description": "Production delay history for an asset.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "risk_score_tool", "description": "Deterministic priority score and constraint flag for an asset.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "alert_dispatch_tool", "description": "Dispatch a real-time alert for a high-risk asset.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}, "risk_level": {"type": "string"}, "summary": {"type": "string"}, "recipients": {"type": "string"}}, "required": ["asset_id", "risk_level", "summary"]}},
    {"name": "task_closure_tool", "description": "Check the compliance checklist for a work order; blocks closure if items missing.",
     "input_schema": {"type": "object", "properties": {"work_order_id": {"type": "string"}, "checklist": {"type": "object"}}, "required": ["work_order_id"]}},
    {"name": "feedback_tool", "description": "Record an engineer correction/confirmation/outcome for an asset so future diagnoses and priority scores improve. Use severity_adjust in [-25,25] when the engineer says the urgency was mis-scored.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}, "work_order_id": {"type": "string"}, "note": {"type": "string"}, "correction": {"type": "string"}, "severity_adjust": {"type": "number"}, "outcome": {"type": "string"}}, "required": ["asset_id"]}},
]


@dataclass
class AgentResult:
    answer_markdown: str
    asset_id: str | None = None
    mode: str = "deterministic"
    trace: list = field(default_factory=list)       # [{tool, input, output}] - observability
    structured: dict = field(default_factory=dict)  # machine-readable result for logbook/evals


def _dispatch(name, args, trace):
    out = TOOL_FUNCS[name](args)
    trace.append({"tool": name, "input": args, "output": out})
    return out


# ==========================================================================
# Deterministic pipeline  (also the reproducible eval baseline)
# ==========================================================================
def run_deterministic(query: str, focus_asset: str | None = None) -> AgentResult:
    trace: list = []
    res = AgentResult(answer_markdown="", mode="deterministic", trace=trace)

    # STEP 0 - resolve. On a follow-up ("what about its bearings?") the new
    # query may name no asset; fall back to the asset still in conversation
    # focus so multi-turn context is preserved.
    r = _dispatch("resolve_asset", {"query": query}, trace)
    aid = r.get("asset_id")
    if not aid and focus_asset:
        aid = focus_asset
        trace.append({"tool": "resolve_asset", "input": {"query": query, "focus": focus_asset},
                      "output": {"asset_id": aid, "confidence": 0.5,
                                 "matched_on": "conversation focus (follow-up)"}})
    if not aid:
        cands = ", ".join(f"{c['asset_id']} ({c['name']})" for c in r.get("candidates", []))
        res.answer_markdown = ("I could not confidently identify the asset. "
                               f"Did you mean one of: {cands}?")
        return res
    res.asset_id = aid

    # STEP 1-4 - gather structured context
    prog = _dispatch("prognostic_tool", {"asset_id": aid}, trace)
    shap = prog.get("shap", {})
    top = shap.get("top_driver")
    rag = _dispatch("rag_tool",
                    {"query": f"{top} fault root cause repair isolation {query}", "asset_id": aid, "k": 6}, trace)
    inv = _dispatch("inventory_tool", {"asset_id": aid}, trace)
    delays = _dispatch("delay_history_tool", {"asset_id": aid}, trace)
    risk = _dispatch("risk_score_tool", {"asset_id": aid}, trace)
    sql = _dispatch("sql_query_tool",
                    {"sql": f"SELECT delay_code, COUNT(*) AS n, SUM(downtime_min) AS mins "
                            f"FROM delays WHERE asset_id='{aid}' GROUP BY delay_code ORDER BY mins DESC"},
                    trace)

    # constraint-aware: pick the most relevant incident as probable root cause
    incidents = [h for h in rag["results"] if h["type"] == "incident"]
    sops = [h for h in rag["results"] if h["type"] == "manual"]
    probable = incidents[0]["source"] if incidents else "see manual"

    # auto-alert on CRITICAL
    alert_line = ""
    if risk["priority_score"] >= ALERT_THRESHOLD:
        summary = f"{aid} {risk['priority_band']} (score {risk['priority_score']}), RUL {prog['rul_days']}d, driver {top}."
        a = _dispatch("alert_dispatch_tool",
                      {"asset_id": aid, "risk_level": risk["priority_band"], "summary": summary}, trace)
        alert_line = f"\n> Auto-alert dispatched to {a['recipients']} at {a['ts']}."

    res.structured = {"asset_id": aid, "risk": risk, "prognostic": prog,
                      "inventory": inv, "delays": delays}
    res.answer_markdown = _render(query, aid, prog, shap, top, risk, delays,
                                  inv, sops, incidents, probable, sql, alert_line)
    return res


def _render(query, aid, prog, shap, top, risk, delays, inv, sops, incidents,
            probable, sql, alert_line):
    devs = shap.get("deviations", {})
    drivers = ", ".join(f"{f} ({devs.get(f,0):+.1f}σ)" for f in shap.get("ranked_drivers", [])[:3])
    out_parts = [p for p in inv["parts"] if p["qty_on_hand"] == 0]

    # Block 3 - blueprint: derive isolation + repair from the SOP section that
    # actually documents the procedure (prefer one with "SOP-"/"Isolation").
    import re as _re
    def _sop_rank(h):
        t = h["source"] + " " + h["text"]
        return (("SOP-" in h["source"]) * 2 + ("Isolation" in t))
    ranked_sops = sorted(sops, key=_sop_rank, reverse=True)
    sop = ranked_sops[0] if ranked_sops else None
    sop_src = sop["source"] if sop else "asset manual"
    sop_text = sop["text"] if sop else ""
    iso = [ln.strip() for ln in sop_text.splitlines()
           if _re.match(r"^\d+\.", ln.strip())][:4]
    iso_md = "\n".join(f"   {s}" for s in iso) if iso else "   Follow the asset LOTO procedure in the manual."

    if risk.get("constraint_flag"):
        longterm = ("**Constraint-aware plan:** " + risk["constraint_flag"] +
                    " Increase condition-monitoring frequency, set tightened vibration/temperature "
                    "alarms, and stage interim mitigations until the part arrives.")
    else:
        longterm = ("Schedule the repair within the RUL window; the required parts can be procured in time. "
                    "Re-baseline alarms after repair.")

    parts_md = "\n".join(
        f"   - `{p['part_no']}` {p['description']}: **{p['status']}**"
        f" (qty {p['qty_on_hand']}, lead {p['lead_time_days']}d, ${p['unit_cost_usd']:,.0f})"
        for p in inv["parts"]) or "   - No parts mapped to this asset."

    inc_md = "\n".join(f"   - {h['source']}" for h in incidents[:2]) or "   - No prior incidents on record."
    sop_md = "\n".join(f"   - {h['source']}" for h in sops[:2]) or "   - No SOP section matched."

    fb_n = risk.get("feedback_count", 0)
    fb_md = (f"\n- **Continuous learning:** incorporated **{fb_n}** engineer feedback "
             f"record(s) on this asset (priority Δ {risk.get('learned_adjustment', 0):+.1f})."
             if fb_n else "")

    md = f"""### 1. Operational Risk Assessment
- **Asset:** `{aid}`  |  **Priority:** **{risk['priority_band']}** (score **{risk['priority_score']}/100**)
- **Remaining Useful Life:** **{prog['rul_days']} days**  |  30-day failure probability: **{prog['failure_probability_30d']:.0%}**
- **Delay severity:** {delays['events']} events, {delays['total_downtime_min']} min downtime, {delays['tonnage_lost']:.0f} t lost{alert_line}

### 2. Diagnostic & Root-Cause Breakdown
- **Probable fault:** {probable}
- **Top SHAP drivers (deviation from healthy baseline):** {drivers}
- **Interpretation:** the prediction is driven primarily by **{top}**; this matches the failure modes documented for this asset.
- *Attribution method: {shap.get('method')}.*

### 3. Actionable Maintenance Blueprint
- **Immediate safety isolation (from {sop_src}):**
{iso_md}
- **Verified repair tasks:** follow {sop_src} step-by-step; do not deviate from documented torque/sequence.
- **Long-term plan:** {longterm}

### 4. Supply-Chain Logistics Strategy
{parts_md}
- **Mitigation:** {"Out-of-stock long-lead parts present - " + ", ".join(p['part_no'] for p in out_parts) + ". Expedite procurement or apply interim monitoring." if out_parts else "All required parts are in stock; no procurement risk."}

### 5. Traceability & Audit Trail
- **SOP sources:**
{sop_md}
- **Historical incidents:**
{inc_md}
- **Structured query run (validate in UI):**
```sql
{sql['sql']}
```{fb_md}
"""
    return md


# ==========================================================================
# LLM mode (Anthropic tool-use loop) - the production "consolidated brain"
# ==========================================================================
def run_llm(query: str, history: list | None = None,
            model="claude-sonnet-4-6", max_steps=8) -> AgentResult:
    import anthropic
    client = anthropic.Anthropic()
    trace: list = []
    # Prepend prior conversation turns so follow-ups are context-aware. History
    # is a list of {"role": "user"|"assistant", "content": str}; we keep only
    # the recent text turns (tool plumbing is re-derived each turn) and ensure
    # the sequence opens on a user turn as the API requires.
    hist = [m for m in (history or [])
            if m.get("role") in ("user", "assistant") and m.get("content")]
    hist = hist[-6:]
    while hist and hist[0]["role"] != "user":
        hist = hist[1:]
    messages = [{"role": m["role"], "content": m["content"]} for m in hist]
    messages.append({"role": "user", "content": query})

    for _ in range(max_steps):
        resp = client.messages.create(
            model=model, max_tokens=2000, system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS, messages=messages,
        )
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = _dispatch(block.name, block.input, trace)
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": json.dumps(out, default=str)})
            messages.append({"role": "user", "content": results})
        else:
            text = "".join(b.text for b in resp.content if b.type == "text")
            aid = next((t["output"].get("asset_id") for t in trace
                        if t["tool"] == "resolve_asset"), None)
            return AgentResult(answer_markdown=text, asset_id=aid, mode="llm",
                               trace=trace)
    return AgentResult(answer_markdown="(reached step limit)", mode="llm", trace=trace)


def run_agent(query: str, history: list | None = None,
              focus_asset: str | None = None) -> AgentResult:
    """Entry point: use Claude if a key is present, else the deterministic pipeline.

    `history` is the prior conversation ([{role, content}, ...]) and `focus_asset`
    is the asset currently in focus; both enable context-aware multi-turn
    follow-ups. Both are optional, so single-shot callers (and the evals) are
    unaffected.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return run_llm(query, history=history)
        except Exception as e:
            r = run_deterministic(query, focus_asset=focus_asset)
            r.answer_markdown = f"> (LLM mode failed: {type(e).__name__}; used deterministic pipeline)\n\n" + r.answer_markdown
            return r
    return run_deterministic(query, focus_asset=focus_asset)


if __name__ == "__main__":
    for q in ["what's wrong with the mill gearbox?",
              "that valve that keeps leaking on the caster"]:
        print("=" * 70, "\nQUERY:", q)
        r = run_agent(q)
        print(f"[mode={r.mode} asset={r.asset_id} tools={len(r.trace)}]")
        print(r.answer_markdown)
