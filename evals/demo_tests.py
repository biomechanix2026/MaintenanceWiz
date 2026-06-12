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
# Serverless core (web/api/_core.py)
# ---------------------------------------------------------------------------
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _core():
    spec = importlib.util.spec_from_file_location(
        "demo_core", _ROOT / "web" / "api" / "_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CHUNKS = [
    {"id": "c1", "asset_id": "GEARBOX-05",
     "source": "Manual GEARBOX-05 - Troubleshooting", "type": "manual",
     "text": "bearing vibration high on gearbox pinion"},
    {"id": "c2", "asset_id": "PUMP-12",
     "source": "Manual PUMP-12 - Troubleshooting", "type": "manual",
     "text": "bearing vibration inspection procedure for pump"},
]


def test_core_rag_filters_by_asset():
    dc = _core()
    dc._cache["chunks"] = _CHUNKS
    dc._cache.pop("bm25", None)
    out = dc.rag_tool("bearing vibration", asset_id="PUMP-12")
    assert [h["source"] for h in out["results"]] == [_CHUNKS[1]["source"]]
    assert out["backend"].startswith("bm25")


def test_core_snapshot_tools_and_unknown_asset():
    dc = _core()
    dc._cache["snapshot"] = {"assets": {"GEARBOX-05": {
        "prognostic": {"rul_days": 12.0}, "abnormality": {"status": "CRITICAL"},
        "risk": {"priority_score": 85.0, "constraint_flag": "LEAD TIME"}}}}
    assert dc.prognostic_tool("GEARBOX-05")["rul_days"] == 12.0
    assert "error" in dc.prognostic_tool("NO-SUCH-99")


def test_core_dispatch_search_returns_sources():
    dc = _core()
    dc._cache["chunks"] = _CHUNKS
    dc._cache.pop("bm25", None)
    result, sources = dc.dispatch("rag_tool", {"query": "bearing vibration"})
    assert result["results"] and sources
    assert sources[0]["source"].startswith("Manual ")


def test_core_dispatch_unknown_tool():
    dc = _core()
    result, sources = dc.dispatch("no_such_tool", {})
    assert "error" in result and sources is None


def test_core_alert_is_always_dry_run():
    dc = _core()
    out, _ = dc.dispatch("alert_dispatch_tool", {
        "asset_id": "GEARBOX-05", "risk_level": "CRITICAL", "summary": "x"})
    assert out["dry_run"] is True and out["dispatched"] is False
    assert out["recipients"] == "shift-supervisor@plant.local"


def test_core_sql_guard_rejects_writes():
    dc = _core()
    out, _ = dc.dispatch("sql_query_tool", {"sql": "DELETE FROM parts"})
    assert "error" in out


def test_core_task_closure_pure():
    dc = _core()
    out, _ = dc.dispatch("task_closure_tool", {"work_order_id": "WO-1"})
    assert out["can_close"] is False and out["completion_blocked_by"]


def test_core_rate_limiter():
    dc = _core()
    dc._hits.clear()
    now = 1000.0
    for _ in range(dc.RATE_LIMIT):
        assert dc.rate_limited("1.2.3.4", now=now) is False
    assert dc.rate_limited("1.2.3.4", now=now) is True
    assert dc.rate_limited("5.6.7.8", now=now) is False
    assert dc.rate_limited("1.2.3.4", now=now + dc.RATE_WINDOW + 1) is False


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
