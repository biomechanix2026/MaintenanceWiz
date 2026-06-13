"""
Conformance tests for the cascade/planner Streamlit helper surfaces.

Run:  python -m evals.ui_surface_tests
"""
from __future__ import annotations

from evals._harness import Suite, run_suites

suite = Suite("ui-surfaces")


@suite.case
def test_UI1_topology_dot_contains_system_priority_and_edges():
    from app.cascade_ui import build_topology_dot

    rows = [
        {"asset_id": "GEARBOX-05", "name": "Mill Drive Gearbox 5",
         "band": "CRITICAL", "system_priority": 95.3},
        {"asset_id": "ROLL-MILL-04", "name": "Hot Strip Roll Mill 4",
         "band": "HIGH", "system_priority": 82.0},
    ]
    dot = build_topology_dot(rows, {"GEARBOX-05": ["ROLL-MILL-04"]})

    assert dot.startswith("digraph plant_topology"), dot
    assert "GEARBOX-05" in dot and "sys 95.3" in dot, dot
    assert "ROLL-MILL-04" in dot and "sys 82.0" in dot, dot
    assert '"GEARBOX-05" -> "ROLL-MILL-04"' in dot, dot
    assert "#FF4D4F" in dot and "#FF9F1C" in dot, dot


@suite.case
def test_UI2_capacity_summary_reports_skill_utilisation():
    from app.cascade_ui import capacity_summary

    text = capacity_summary({
        "by_skill": {
            "mechanical": {"total": 16.0, "used": 14.5, "left": 1.5},
            "hydraulic": {"total": 8.0, "used": 2.5, "left": 5.5},
        }
    })

    assert "mechanical 14.5/16.0h used (1.5h left)" in text, text
    assert "hydraulic 2.5/8.0h used (5.5h left)" in text, text
    assert " | " in text, text


@suite.case
def test_UI3_plan_bucket_rows_are_table_ready():
    from app.cascade_ui import plan_bucket_rows

    plan = {
        "scheduled": [{"asset_id": "PUMP-12", "task": "Seal service",
                       "crew_id": "M-HYD-1", "est_hours": 3.0,
                       "system_priority": 98.9}],
        "deferred": [{"asset_id": "ROLL-MILL-11",
                      "reason": "no mechanical crew has 5.0h free",
                      "system_priority": 71.0}],
        "procurement": [{"asset_id": "GEARBOX-05",
                         "reason": "LEAD TIME EXCEEDS RUL",
                         "system_priority": 95.3}],
    }

    scheduled = plan_bucket_rows(plan, "scheduled")
    deferred = plan_bucket_rows(plan, "deferred")
    procurement = plan_bucket_rows(plan, "procurement")

    assert scheduled == [{"Asset": "PUMP-12", "Task": "Seal service",
                          "Crew": "M-HYD-1", "Hours": 3.0,
                          "System Priority": 98.9}], scheduled
    assert deferred[0]["Reason"].startswith("no mechanical crew"), deferred
    assert procurement[0]["Reason"] == "LEAD TIME EXCEEDS RUL", procurement


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
