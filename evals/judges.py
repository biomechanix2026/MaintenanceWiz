"""
Observability-driven evals ("judges").

Following the Omni pattern: capture the agent's trace on a fixed input and run
automated judges that assert the decision lands in the expected band. These
guard against silent regressions when the system prompt, tools or model change.

Each case checks the structured result and the tool trace, not the exact prose,
so the judge is robust to wording changes but strict about logic.

Run:  python -m evals.judges
"""
from __future__ import annotations
import sys

# Force UTF-8 stdout so the check/cross marks below don't crash on the default
# Windows console encoding (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agent.orchestrator import run_deterministic

CASES = [
    {
        "name": "gearbox-critical-constraint",
        "query": "what's wrong with the mill gearbox?",
        "expect_asset": "GEARBOX-05",
        "expect_band_in": {"CRITICAL", "HIGH"},
        "expect_constraint_flag": True,      # 45d pinion lead > RUL
        "expect_tool_called": "risk_score_tool",
        "expect_alert_recommended": True,    # CRITICAL -> alert recommended (no side effect)
    },
    {
        "name": "valve-fuzzy-resolution",
        "query": "that valve that keeps leaking on the caster",
        "expect_asset": "HYD-VALVE-07",
        "expect_band_in": {"HIGH", "CRITICAL"},
        "expect_constraint_flag": False,     # spool lead 18d < RUL
        "expect_tool_called": "resolve_asset",
    },
    {
        "name": "healthy-crane-low",
        "query": "status of the charge bay crane",
        "expect_asset": "CRANE-06",
        "expect_band_in": {"LOW", "MEDIUM"},
        "expect_constraint_flag": False,
        "expect_tool_called": "prognostic_tool",
    },
    {
        "name": "abbreviation-eaf",
        "query": "check the EAF",
        "expect_asset": "FURNACE-01",
        "expect_band_in": {"LOW", "MEDIUM", "HIGH"},
        "expect_constraint_flag": False,
        "expect_tool_called": "risk_score_tool",
    },
]


def judge(case):
    res = run_deterministic(case["query"])
    risk = res.structured.get("risk", {})
    tools_called = {t["tool"] for t in res.trace}
    checks = {
        "asset_resolved": res.asset_id == case["expect_asset"],
        "band_ok": risk.get("priority_band") in case["expect_band_in"],
        "constraint_ok": bool(risk.get("constraint_flag")) == case["expect_constraint_flag"],
        "tool_called": case["expect_tool_called"] in tools_called,
        "five_blocks": all(f"### {i}." in res.answer_markdown for i in range(1, 6)),
    }
    if "expect_alert_recommended" in case:
        checks["alert_recommended"] = (
            bool(res.structured.get("alert_recommended")) == case["expect_alert_recommended"])
    return all(checks.values()), checks, res


def main():
    print("=" * 64)
    print("MAINTENANCE WIZARD - EVAL JUDGES")
    print("=" * 64)
    passed = 0
    for c in CASES:
        ok, checks, res = judge(c)
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"\n[{status}] {c['name']}  (asset={res.asset_id})")
        for k, v in checks.items():
            print(f"     {'✓' if v else '✗'} {k}")
    print("\n" + "-" * 64)
    print(f"RESULT: {passed}/{len(CASES)} judges passed")
    sys.exit(0 if passed == len(CASES) else 1)


if __name__ == "__main__":
    main()
