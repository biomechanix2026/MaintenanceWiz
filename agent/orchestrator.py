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
    "fault_mode_tool": lambda a: T.fault_mode_tool(
        a["air_temperature_K"], a["process_temperature_K"], a["rotational_speed_rpm"],
        a["torque_Nm"], a["tool_wear_min"], a.get("machine_type", "M")),
    "abnormality_tool": lambda a: T.abnormality_tool(a["asset_id"]),
    "rag_tool": lambda a: T.rag_tool(a["query"], a.get("asset_id"), a.get("k", 4)),
    "inventory_tool": lambda a: T.inventory_tool(a["asset_id"]),
    "sql_query_tool": lambda a: T.sql_query_tool(a["sql"]),
    "delay_history_tool": lambda a: T.delay_history_tool(a["asset_id"]),
    "risk_score_tool": lambda a: T.risk_score_tool(a["asset_id"]),
    "cascade_tool": lambda a: T.cascade_tool(a["asset_id"]),
    "shift_plan_tool": lambda a: T.shift_plan_tool(),
    "work_order_draft_tool": lambda a: T.work_order_draft_tool(a.get("persist", False)),
    "cost_tool": lambda a: T.cost_tool(a["asset_id"]),
    "risk_simulator_tool": lambda a: T.risk_simulator_tool(a.get("trials")),
    "alert_dispatch_tool": lambda a: T.alert_dispatch_tool(
        a["asset_id"], a["risk_level"], a["summary"], a.get("recipients"),
        role=a.get("role"), dry_run=a.get("dry_run", not _ALERTS_LIVE)),
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
    {"name": "fault_mode_tool",
     "description": "Classify failure risk and probable failure mode (TWF/HDF/PWF/OSF/RNF) from machine operating parameters. Call when the engineer provides operating readings to assess.",
     "input_schema": {"type": "object", "properties": {
         "air_temperature_K": {"type": "number"},
         "process_temperature_K": {"type": "number"},
         "rotational_speed_rpm": {"type": "number"},
         "torque_Nm": {"type": "number"},
         "tool_wear_min": {"type": "number"},
         "machine_type": {"type": "string", "enum": ["L", "M", "H"]}},
      "required": ["air_temperature_K", "process_temperature_K", "rotational_speed_rpm",
                   "torque_Nm", "tool_wear_min"]}},
    {"name": "abnormality_tool", "description": "Independent dynamic abnormality detection from sensor deviations and trend.",
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
    {"name": "cascade_tool",
     "description": "Plant-level cascade impact for an asset: downstream assets idled by its failure, blast radius, and system_priority (own priority escalated by downstream criticality). Call after risk_score_tool to express plant bottleneck impact.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "shift_plan_tool",
     "description": "Propose the next-shift action queue for the whole plant: ranks flagged assets by system_priority (cascade-aware), allocates finite crew-hours per skill, defers what does not fit (with reasons), and diverts parts-infeasible jobs to monitored degradation + procurement. Use for plant-scope questions like 'what should we do this shift?' - takes no arguments.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "work_order_draft_tool",
     "description": "Draft one trace-backed DRAFT work order per scheduled next-shift job (composes shift_plan_tool + risk/cascade/spares/SOP evidence + crew + planned hours). Parts-infeasible/deferred jobs get none. Approval-gated: drafts only, never auto-closed. Pass persist=true to write JSON artifacts (opt-in side effect); default is side-effect-free.",
     "input_schema": {"type": "object", "properties": {"persist": {"type": "boolean"}}}},
    {
        "name": "cost_tool",
        "description": ("Estimated expected event-cost proxy, the feasible maintenance "
                        "action, and the expected value preserved (act now vs. run to "
                        "failure) for one asset. Dollar figures come only from this tool."),
        "input_schema": {"type": "object",
                         "properties": {"asset_id": {"type": "string"}},
                         "required": ["asset_id"]},
    },
    {
        "name": "risk_simulator_tool",
        "description": ("Seeded Monte-Carlo plant-risk distribution (expected monetary "
                        "loss percentile bands) and a ranked list of FEASIBLE next-shift "
                        "actions. repair_now rows report estimated value preserved; "
                        "procurement/monitor rows report value at risk. Plant-scope; no asset_id."),
        "input_schema": {"type": "object",
                         "properties": {"trials": {"type": "integer"}},
                         "required": []},
    },
    {"name": "alert_dispatch_tool", "description": "Dispatch a real-time, role-routed alert for a high-risk asset. Omit recipients to auto-route by severity (critical->supervisor, high->reliability, else maintenance); or pass role (maintenance|reliability|supervisor) or an explicit recipients string.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}, "risk_level": {"type": "string"}, "summary": {"type": "string"}, "recipients": {"type": "string"}, "role": {"type": "string"}}, "required": ["asset_id", "risk_level", "summary"]}},
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
    citations: list = field(default_factory=list)   # Anthropic citation metadata, LLM mode only


# Live-alert toggle. A plain diagnostic query is side-effect-free: alert
# dispatch is dry-run unless a caller (monitoring / pre-shift) opts in with
# dispatch_alerts=True. Module-global because Streamlit runs single-threaded.
_ALERTS_LIVE = False


def _dispatch(name, args, trace):
    out = TOOL_FUNCS[name](args)
    trace.append({"tool": name, "input": args, "output": out})
    return out


def _doc_blocks_from_rag(results: list[dict]) -> list[dict]:
    """Convert RAG hits into Anthropic document blocks with citations enabled."""
    blocks = []
    for hit in results:
        blocks.append({
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": hit["text"],
            },
            "title": str(hit.get("source", "doc"))[:255],
            "context": json.dumps({
                "asset_id": hit.get("asset_id"),
                "type": hit.get("type"),
            }),
            "citations": {"enabled": True},
        })
    return blocks


# ==========================================================================
# Deterministic pipeline  (also the reproducible eval baseline)
# ==========================================================================
def run_deterministic(query: str, focus_asset: str | None = None,
                      dispatch_alerts: bool = False) -> AgentResult:
    global _ALERTS_LIVE
    _ALERTS_LIVE = dispatch_alerts
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
    abnormality = _dispatch("abnormality_tool", {"asset_id": aid}, trace)
    shap = prog.get("shap", {})
    top = shap.get("top_driver")
    abn_top = (abnormality.get("top_drivers") or [None])[0]
    rag = _dispatch("rag_tool",
                    {"query": f"{top} {abn_top} abnormal fault root cause repair isolation {query}",
                     "asset_id": aid, "k": 6}, trace)
    inv = _dispatch("inventory_tool", {"asset_id": aid}, trace)
    delays = _dispatch("delay_history_tool", {"asset_id": aid}, trace)
    risk = _dispatch("risk_score_tool", {"asset_id": aid}, trace)
    casc = _dispatch("cascade_tool", {"asset_id": aid}, trace)
    cost = _dispatch("cost_tool", {"asset_id": aid}, trace)
    sql = _dispatch("sql_query_tool",
                    {"sql": f"SELECT delay_code, COUNT(*) AS n, SUM(downtime_min) AS mins "
                            f"FROM delays WHERE asset_id='{aid}' GROUP BY delay_code ORDER BY mins DESC"},
                    trace)

    # constraint-aware: pick the most relevant incident as probable root cause
    incidents = [h for h in rag["results"] if h["type"] == "incident"]
    sops = [h for h in rag["results"] if h["type"] == "manual"]
    probable = incidents[0]["source"] if incidents else "see manual"

    # Alert decision is computed on every query, but dispatching is a side
    # effect reserved for opt-in monitoring (dispatch_alerts=True). A plain
    # diagnostic query only *recommends* the alert.
    alert_recommended = risk["priority_score"] >= ALERT_THRESHOLD
    alert_line = ""
    if alert_recommended:
        summary = f"{aid} {risk['priority_band']} (score {risk['priority_score']}), RUL {prog['rul_days']}d, driver {top}."
        if dispatch_alerts:
            a = _dispatch("alert_dispatch_tool",
                          {"asset_id": aid, "risk_level": risk["priority_band"], "summary": summary}, trace)
            alert_line = (f"\n> Auto-alert dispatched to {a['recipients']} at {a['ts']}."
                          if a.get("dispatched")
                          else "\n> Auto-alert recommended (already sent today — deduped).")
        else:
            alert_line = "\n> **Auto-alert recommended** (CRITICAL) — dispatch on confirmation."

    res.structured = {"asset_id": aid, "risk": risk, "cascade": casc, "prognostic": prog,
                      "abnormality": abnormality,
                      "inventory": inv, "delays": delays, "cost": cost,
                      "alert_recommended": alert_recommended}
    res.answer_markdown = _render(query, aid, prog, shap, top, abnormality, risk, delays,
                                  inv, sops, incidents, probable, sql, alert_line, casc, cost)
    return res


def _render(query, aid, prog, shap, top, abnormality, risk, delays, inv, sops, incidents,
            probable, sql, alert_line, casc, cost=None):
    devs = shap.get("deviations", {})
    drivers = ", ".join(f"{f} ({devs.get(f,0):+.1f}σ)" for f in shap.get("ranked_drivers", [])[:3])
    out_parts = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
    abn_status = abnormality.get("status", "UNKNOWN")
    abn_score = abnormality.get("anomaly_score", 0)
    abn_breaches = abnormality.get("breached_features", [])
    abn_drivers = ", ".join(
        f"{b['feature']} ({b['deviation_z']:+.1f}z {b['level']})"
        for b in abn_breaches[:3]) or "no feature above warning threshold"
    trend = abnormality.get("trend_features", [])
    trend_md = ("; ".join(f"{t['feature']} {t['direction']} ({t['trend_delta_z']:+.1f}z)"
                          for t in trend[:2]) if trend else "no short-window trend breach")
    catastrophic = "yes" if abnormality.get("catastrophic_risk") else "no"

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

    if casc.get("downstream_count"):
        system_line = (f"\n- **System impact:** idles **{casc['downstream_count']}** downstream asset(s) -> "
                       f"system priority **{casc['system_priority']}/100** "
                       f"(blast radius {casc['blast_radius']})")
        casc_md = f"\n- **Cascade path:** `{casc['path_str']}`"
    else:
        system_line = "\n- **System impact:** terminal asset - no downstream dependents"
        casc_md = ""

    # Financial exposure (Block 1) + value preserved / at risk (Block 4). Additive,
    # tool-grounded; dollars come only from cost_tool (never invented). repair_now is
    # the only action that preserves value this shift; others are exposed value at risk.
    cost_line1 = cost_line4 = ""
    if cost and "error" not in cost:
        ec = cost["event_cost_proxy"]
        cost_line1 = (f"\n- **Estimated exposure:** ~${cost['failure_cost_usd']:,.0f} expected "
                      f"event-cost proxy (cascade-coupled); single-event proxy "
                      f"~${ec['total_usd']:,.0f}")
        v = cost["emv"]
        f_ = cost["feasibility"]
        if f_["action"] == "repair_now":
            cost_line4 = (f"\n- **Estimated value preserved by repair_now:** "
                          f"~${v['expected_value_preserved_usd']:,.0f} (expected run-to-failure "
                          f"loss ~${v['expected_failure_loss_usd']:,.0f}); counterfactual "
                          f"estimate under stated assumptions.")
        else:
            cost_line4 = (f"\n- **Estimated value at risk pending {f_['action']}:** "
                          f"~${v['expected_failure_loss_usd']:,.0f}; exposed risk, not value "
                          f"preserved this shift.")

    fb_n = risk.get("feedback_count", 0)
    fb_md = (f"\n- **Continuous learning:** {fb_n} engineer feedback record(s) on this "
             f"asset re-indexed as advisory context"
             + (f" (priority Δ applied: {risk.get('learned_adjustment', 0):+.1f})."
                if risk.get("feedback_bias_applied") else " (priority score unaffected).")
             if fb_n else "")

    md = f"""### 1. Operational Risk Assessment
- **Asset:** `{aid}`  |  **Priority:** **{risk['priority_band']}** (score **{risk['priority_score']}/100**)
- **Remaining Useful Life:** **{prog['rul_days']} days**  |  30-day failure probability: **{prog['failure_probability_30d']:.0%}**
- **Independent abnormality detector:** **{abn_status}** (score **{abn_score}/100**; catastrophic risk: **{catastrophic}**)
- **Delay severity:** {delays['events']} events, {delays['total_downtime_min']} min downtime, {delays['tonnage_lost']:.0f} t lost{alert_line}{system_line}{cost_line1}

### 2. Diagnostic & Root-Cause Breakdown
- **Probable fault:** {probable}
- **Top SHAP drivers (deviation from healthy baseline):** {drivers}
- **Abnormal sensor evidence:** {abn_drivers}; trend: {trend_md}
- **Interpretation:** the prediction is driven primarily by **{top}**; this matches the failure modes documented for this asset.
- *Attribution method: {shap.get('method')}; abnormality thresholds: warning >= {abnormality.get('thresholds', {}).get('warning_z')}z, critical >= {abnormality.get('thresholds', {}).get('critical_z')}z.*

### 3. Actionable Maintenance Blueprint
- **Immediate safety isolation (from {sop_src}):**
{iso_md}
- **Verified repair tasks:** follow {sop_src} step-by-step; do not deviate from documented torque/sequence.
- **Long-term plan:** {longterm}

### 4. Supply-Chain Logistics Strategy
{parts_md}
- **Mitigation:** {"Out-of-stock long-lead parts present - " + ", ".join(p['part_no'] for p in out_parts) + ". Expedite procurement or apply interim monitoring." if out_parts else "All required parts are in stock; no procurement risk."}{cost_line4}

### 5. Traceability & Audit Trail
- **SOP sources:**
{sop_md}
- **Historical incidents:**
{inc_md}
- **Structured query run (validate in UI):**
```sql
{sql['sql']}
```{casc_md}{fb_md}
"""
    return md


# ==========================================================================
# LLM mode (Anthropic tool-use loop) - the production "consolidated brain"
# ==========================================================================
def _structured_from_trace(trace: list, asset_id: str | None) -> dict:
    """Mirror the deterministic `structured` contract from the LLM tool trace so
    both modes hand the UI/logbook the same machine-readable result."""
    def last(tool):
        return next((t["output"] for t in reversed(trace) if t["tool"] == tool), None)
    risk = last("risk_score_tool") or {}
    out = {"asset_id": asset_id, "risk": risk,
           "cascade": last("cascade_tool"),
           "prognostic": last("prognostic_tool"),
           "abnormality": last("abnormality_tool"),
           "inventory": last("inventory_tool"),
           "delays": last("delay_history_tool")}
    cost = next((t["output"] for t in reversed(trace)
                 if t["tool"] == "cost_tool" and "error" not in (t.get("output") or {})), None)
    if cost is not None:
        out["cost"] = cost
    if risk.get("priority_score") is not None:
        out["alert_recommended"] = risk["priority_score"] >= ALERT_THRESHOLD
    return {k: v for k, v in out.items() if v is not None}


def run_llm(query: str, history: list | None = None,
            model="claude-sonnet-4-6", max_steps=8,
            focus_asset: str | None = None,
            dispatch_alerts: bool = False) -> AgentResult:
    global _ALERTS_LIVE
    _ALERTS_LIVE = dispatch_alerts
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
    # Carry the in-focus asset into follow-ups so LLM mode resolves anaphora the
    # same way deterministic mode does.
    user_content = query
    if focus_asset and hist:
        user_content = f"{query}\n\n(Context: the asset currently in focus is {focus_asset}.)"
    messages.append({"role": "user", "content": user_content})

    for _ in range(max_steps):
        resp = client.messages.create(
            model=model, max_tokens=2000,
            system=[{"type": "text", "text": SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            tools=TOOL_SCHEMAS, messages=messages,
        )
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results, doc_blocks = [], []
            for block in resp.content:
                if block.type == "tool_use":
                    out = _dispatch(block.name, block.input, trace)
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": json.dumps(out, default=str)})
                    if block.name == "rag_tool":
                        doc_blocks.extend(_doc_blocks_from_rag(out.get("results", [])))
            messages.append({"role": "user", "content": results + doc_blocks})
        else:
            text = "".join(b.text for b in resp.content if b.type == "text")
            citations = []
            for b in resp.content:
                if getattr(b, "type", None) == "text":
                    for c in getattr(b, "citations", None) or []:
                        citations.append({
                            "cited_text": c.cited_text,
                            "document_title": c.document_title,
                            "document_index": c.document_index,
                        })
            aid = next((t["output"].get("asset_id") for t in trace
                        if t["tool"] == "resolve_asset" and t["output"].get("asset_id")),
                       focus_asset)
            return AgentResult(answer_markdown=text, asset_id=aid, mode="llm",
                               trace=trace, structured=_structured_from_trace(trace, aid),
                               citations=citations)
    return AgentResult(answer_markdown="(reached step limit)", mode="llm", trace=trace,
                       structured=_structured_from_trace(trace, focus_asset))


def run_agent(query: str, history: list | None = None,
              focus_asset: str | None = None,
              dispatch_alerts: bool = False) -> AgentResult:
    """Entry point: use Claude if a key is present, else the deterministic pipeline.

    `history` is the prior conversation ([{role, content}, ...]) and `focus_asset`
    is the asset currently in focus; both enable context-aware multi-turn
    follow-ups. `dispatch_alerts` opts into live alert dispatch (default off, so
    a diagnostic query is side-effect-free). All optional, so single-shot callers
    (and the evals) are unaffected.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return run_llm(query, history=history, focus_asset=focus_asset,
                           dispatch_alerts=dispatch_alerts)
        except Exception as e:
            r = run_deterministic(query, focus_asset=focus_asset, dispatch_alerts=dispatch_alerts)
            r.answer_markdown = f"> (LLM mode failed: {type(e).__name__}; used deterministic pipeline)\n\n" + r.answer_markdown
            return r
    return run_deterministic(query, focus_asset=focus_asset, dispatch_alerts=dispatch_alerts)


if __name__ == "__main__":
    for q in ["what's wrong with the mill gearbox?",
              "that valve that keeps leaking on the caster"]:
        print("=" * 70, "\nQUERY:", q)
        r = run_agent(q)
        print(f"[mode={r.mode} asset={r.asset_id} tools={len(r.trace)}]")
        print(r.answer_markdown)
