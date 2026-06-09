"""
Problem-statement integration judges via the deterministic pipeline.

Reproducible without an API key: run_deterministic() exercises the full
think->act->observe pipeline. Assertions check structured fields, the trace,
the five output blocks, and cited evidence - never exact prose.

Run:  python -m evals.requirement_judges
"""
from __future__ import annotations
import os

from agent.orchestrator import run_deterministic, run_agent, TOOL_SCHEMAS, TOOL_FUNCS
from agent import tools as T
from evals._harness import Suite, run_suites, sandbox

suite = Suite("requirement-judges")


def five_blocks(md: str) -> bool:
    return all(f"### {i}." in md for i in range(1, 6))


def tools_in(trace, name):
    return any(t["tool"] == name for t in trace)


# ---- FR-01: contextual reasoning + offline fallback contract --------------
@suite.case
def test_FR01_offline_reasoning_contract():
    r = run_agent("what's wrong with the mill gearbox?")  # no API key -> deterministic
    assert r.mode == "deterministic", r.mode
    assert five_blocks(r.answer_markdown), "missing one of five blocks"
    assert r.structured and r.trace, "empty structured/trace"
    # LLM mode exposes the same tool suite
    assert {s["name"] for s in TOOL_SCHEMAS} == set(TOOL_FUNCS), "schema/func registry mismatch"


# ---- FR-03 / IN-14: multi-turn focus + ambiguity --------------------------
@suite.case
def test_FR03_multiturn_focus_and_ambiguity():
    r1 = run_deterministic("what's wrong with the mill gearbox?")
    assert r1.asset_id == "GEARBOX-05", r1.asset_id
    r2 = run_deterministic("what about its bearings?", focus_asset=r1.asset_id)
    assert r2.asset_id == "GEARBOX-05", "follow-up lost focus"
    assert any("focus" in str(t["output"].get("matched_on", "")) for t in r2.trace), "no focus-fallback trace"
    amb = run_deterministic("the thing seems off today")
    assert amb.asset_id is None and "did you mean" in amb.answer_markdown.lower(), "no clarification on ambiguity"


# ---- FR-04 / EO-06: explainable, traceable recommendation -----------------
@suite.case
def test_FR04_explainable_traceable():
    r = run_deterministic("what's wrong with the mill gearbox?")
    md = r.answer_markdown
    assert five_blocks(md)
    assert "SHAP" in md, "no SHAP evidence"
    assert "abnormality detector" in md.lower(), "no abnormality evidence"
    assert "INC-" in md, "no incident source id cited"
    assert "Manual" in md or "SOP" in md, "no SOP/manual source cited"
    assert "select" in md.lower() and "from delays" in md.lower(), "exact SQL not echoed"
    for tool in ("resolve_asset", "prognostic_tool", "abnormality_tool", "rag_tool",
                 "risk_score_tool", "sql_query_tool"):
        assert tools_in(r.trace, tool), f"trace missing {tool}"


# ---- IN-02: fault/symptom phrasing resolves -------------------------------
@suite.case
def test_IN02_symptom_query_resolves():
    r = run_deterministic("mill gearbox vibration alarm")
    assert r.asset_id == "GEARBOX-05", r.asset_id


# ---- IN-09 / OUT-10 / OUT-11: blueprint sourced from SOP ------------------
@suite.case
def test_IN09_blueprint_sourced():
    md = run_deterministic("what's wrong with the mill gearbox?").answer_markdown
    block3 = md.split("### 3.")[1].split("### 4.")[0]
    assert "isolation" in block3.lower(), "no isolation guidance"
    assert "(from " in block3, "isolation steps not attributed to a source"
    import re
    assert re.search(r"\d+\.", block3) or "LOTO" in block3, "no ordered steps / LOTO fallback"


# ---- IN-12 / DL-04 / EO-03: demo prompts resolve + five blocks ------------
DEMO = {
    "what's wrong with the mill gearbox?": "GEARBOX-05",
    "that valve that keeps leaking on the caster": "HYD-VALVE-07",
    "check the EAF": "FURNACE-01",
    "status of the charge bay crane": "CRANE-06",
    "cooling pump status": "PUMP-12",
}

@suite.case
def test_IN12_demo_scenarios():
    for prompt, expected in DEMO.items():
        r = run_deterministic(prompt)
        assert r.asset_id == expected, f"{prompt!r} -> {r.asset_id} (want {expected})"
        assert five_blocks(r.answer_markdown), f"{prompt!r} missing blocks"
        assert r.trace, f"{prompt!r} empty trace"


# ---- OUT-01 / OUT-02: probable fault + root cause from evidence -----------
@suite.case
def test_OUT01_OUT02_fault_root_cause():
    md = run_deterministic("what's wrong with the cooling pump?").answer_markdown
    block2 = md.split("### 2.")[1].split("### 3.")[0]
    assert "probable fault" in block2.lower(), "no probable fault"
    assert "INC-" in block2 or "see manual" in block2.lower(), "fault not tied to evidence"


# ---- OUT-07: urgency - critical vs healthy --------------------------------
@suite.case
def test_OUT07_urgency_split():
    crit = run_deterministic("what's wrong with the mill gearbox?")
    assert crit.structured["risk"]["priority_band"] in {"CRITICAL", "HIGH"}
    assert crit.structured["alert_recommended"] is True, "critical did not recommend alert"
    healthy = run_deterministic("status of the charge bay crane")
    assert healthy.structured["risk"]["priority_band"] in {"LOW", "MEDIUM"}, healthy.structured["risk"]["priority_band"]
    assert not healthy.structured["risk"].get("constraint_flag"), "healthy asset has constraint flag"


# ---- OUT-12 / OUT-13: optimized plan under constraint ---------------------
@suite.case
def test_OUT12_constraint_plan():
    md = run_deterministic("what's wrong with the mill gearbox?").answer_markdown
    assert "monitored degradation" in md.lower(), "constraint did not switch to monitored degradation"
    assert "monitor" in md.lower(), "no long-term monitoring guidance"


# ---- OUT-17: decision summary contract ------------------------------------
@suite.case
def test_OUT17_decision_summary():
    md = run_deterministic("check the EAF").answer_markdown
    for header in ("Operational Risk", "Diagnostic", "Maintenance Blueprint",
                   "Supply-Chain", "Traceability"):
        assert header in md, f"missing section: {header}"


# ---- EO-04: proactive flagging from sensor/RUL (no incident needed) -------
@suite.case
def test_EO04_proactive_flagging():
    r = run_deterministic("status of the cooling pump")
    md = r.answer_markdown
    assert "remaining useful life" in md.lower(), "no RUL surfaced"
    assert "abnormality detector" in md.lower(), "no abnormality surfaced"
    assert r.structured["abnormality"]["status"] in {"NORMAL", "WARNING", "CRITICAL"}


# ---- IN-13: scenario prompt + feedback persists ---------------------------
@suite.case
def test_IN13_scenario_then_feedback():
    with sandbox():
        r = run_deterministic("the valve that keeps leaking on the caster")
        assert r.asset_id == "HYD-VALVE-07", r.asset_id
        out = T.record_feedback(r.asset_id, note="confirmed spool contamination", outcome="confirmed")
        assert out["recorded"] and out["feedback_count"] == 1, out


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
