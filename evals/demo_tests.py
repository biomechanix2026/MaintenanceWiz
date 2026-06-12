"""Focused tests for the hosted-demo export script and serverless core.

Plain-assert style (this repo has no pytest; `python -m evals.judges` is the
regression guard and this module is its sibling for the web demo).

Run:  python -m evals.demo_tests
"""
from __future__ import annotations
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Export script (scripts/build_demo_assets.py) — pure parts only
# ---------------------------------------------------------------------------
def _good_snapshot(asset_ids):
    return {"generated": "2026-06-12T00:00:00+00:00",
            "assets": {aid: {
                "prognostic": {"asset_id": aid, "rul_days": 50.0,
                               "failure_probability_30d": 0.2, "shap": {}},
                "abnormality": {"asset_id": aid, "status": "NORMAL",
                                "anomaly_score": 10.0},
                "risk": {"asset_id": aid, "priority_score": 40.0,
                         "priority_band": "MEDIUM", "constraint_flag": None},
            } for aid in asset_ids}}


def test_demo_tools_subset_and_gemini_format():
    from scripts.build_demo_assets import demo_tools, EXCLUDED_TOOLS
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    tools = demo_tools()
    names = {t["name"] for t in tools}
    assert EXCLUDED_TOOLS == {"fault_mode_tool", "feedback_tool"}
    assert names.isdisjoint(EXCLUDED_TOOLS)
    assert len(tools) == len(TOOL_SCHEMAS) - len(EXCLUDED_TOOLS)  # 10 of 12
    assert names <= set(TOOL_FUNCS)            # every exported tool is real
    for t in tools:                            # Gemini format, not Anthropic
        assert "parameters" in t and "input_schema" not in t
        assert t["parameters"]["type"] == "object"


def test_validate_snapshot_accepts_good():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1", "B-2"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "LEAD TIME EXCEEDS RUL"
    validate_snapshot(snap, ["A-1", "B-2"])    # must not raise


def test_validate_snapshot_rejects_missing_asset():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "x"
    try:
        validate_snapshot(snap, ["A-1", "B-2"])
    except ValueError:
        return
    raise AssertionError("missing asset not rejected")


def test_validate_snapshot_rejects_out_of_range_score():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "x"
    snap["assets"]["A-1"]["risk"]["priority_score"] = 140.0
    try:
        validate_snapshot(snap, ["A-1"])
    except ValueError:
        return
    raise AssertionError("out-of-range score not rejected")


def test_validate_snapshot_requires_constraint_demo():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])             # no constraint_flag anywhere
    try:
        validate_snapshot(snap, ["A-1"])
    except ValueError:
        return
    raise AssertionError("snapshot without any constraint_flag not rejected")


# ---------------------------------------------------------------------------
# Serverless core (web/api/_core.py) — tests added in Task 3 below this line
# ---------------------------------------------------------------------------


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except Exception as e:
            failures.append((name, e))
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
