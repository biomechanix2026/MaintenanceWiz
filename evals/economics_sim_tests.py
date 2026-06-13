"""
Unit + feasibility conformance for the financial cost engine + risk simulator.
Spec: docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md
Run:  python -m evals.economics_sim_tests
"""
from __future__ import annotations
from evals._harness import Suite, run_suites, approx

suite = Suite("economics-simulator")


# ---- T1: config + job-template part mapping --------------------------------
@suite.case
def test_T1_config_and_job_part_mapping():
    import config as C
    for k in ("TONNAGE_MARGIN_USD_PER_TON", "PLANNED_STOP_COST_FACTOR",
              "DOWNTIME_COST_USD_PER_HOUR", "DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE",
              "DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE", "SIMULATION_TRIALS",
              "SIMULATION_SEED", "CASCADE_EDGE_PROBABILITY_FLOOR",
              "CASCADE_EDGE_PROBABILITY_CAP"):
        assert hasattr(C, k), f"config missing {k}"
    assert 0.0 < C.PLANNED_STOP_COST_FACTOR < 1.0, C.PLANNED_STOP_COST_FACTOR

    import pandas as pd
    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    assert "primary_part_no" in jt.columns, "job_templates.csv missing primary_part_no"
    assert jt["primary_part_no"].notna().all(), "every job needs a primary_part_no"
    parts = pd.read_csv(C.PARTS_CSV)
    known = set(parts["part_no"])
    for pno in jt["primary_part_no"]:
        assert pno in known, f"primary_part_no {pno} not in inventory"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
