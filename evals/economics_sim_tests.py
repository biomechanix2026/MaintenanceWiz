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


# ---- T2: economics core (pure, direct cost only) ---------------------------
@suite.case
def test_T2_direct_event_cost():
    from agent import economics as E
    out = E.direct_event_cost(asset_type="furnace", downtime_min_per_event=60.0,
                              tonnage_lost_per_event=10.0,
                              downtime_cost_usd_per_hour=120000.0,
                              tonnage_margin_usd_per_ton=75.0)
    assert out["downtime_usd"] == 120000.0, out          # 60min = 1h * 120000
    assert out["tonnage_usd"] == 750.0, out               # 10 * 75
    assert out["total_usd"] == 120750.0, out
    assert out["label"] == "expected event-cost proxy", out
    # zero tonnage still has downtime cost
    z = E.direct_event_cost(asset_type="pump", downtime_min_per_event=30.0,
                            tonnage_lost_per_event=0.0,
                            downtime_cost_usd_per_hour=22000.0,
                            tonnage_margin_usd_per_ton=75.0)
    assert z["tonnage_usd"] == 0.0 and z["downtime_usd"] == 11000.0, z


@suite.case
def test_T2_planned_action_and_emv():
    from agent import economics as E
    pac = E.planned_action_cost(planned_hours=4.0, downtime_cost_usd_per_hour=65000.0,
                                planned_stop_cost_factor=0.35,
                                primary_part_unit_cost_usd=7800.0)
    # planned downtime = 4 * 65000 * 0.35 = 91000 ; + part 7800
    assert pac["planned_downtime_usd"] == 91000.0, pac
    assert pac["total_usd"] == 98800.0, pac

    pos = E.emv(p_failure=0.5, failure_cost_usd=300000.0, action_cost_usd=98800.0)
    assert pos["expected_failure_loss_usd"] == 150000.0, pos
    assert pos["expected_value_preserved_usd"] == 51200.0, pos
    assert pos["recommendation"] == "positive_expected_value", pos

    mon = E.emv(p_failure=0.4, failure_cost_usd=5000.0, action_cost_usd=0.0)
    assert mon["recommendation"] == "monitor", mon

    neg = E.emv(p_failure=0.05, failure_cost_usd=1000.0, action_cost_usd=4000.0)
    assert neg["recommendation"] == "not_economic_on_30d_horizon", neg


@suite.case
def test_T2_economics_is_pure():
    import inspect
    from agent import economics as E
    src = inspect.getsource(E)
    for forbidden in ("import pandas", "read_csv", "agent.tools", "build_graph"):
        assert forbidden not in src, f"economics core must not contain {forbidden!r}"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
