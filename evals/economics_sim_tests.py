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


# ---- T3: risk simulator core (seeded, CRN, suppression) --------------------
def _chain_fixture():
    # A -> B -> C, every edge weight 0.6, costs 100 each.
    nodes = ["A", "B", "C"]
    edges = [("A", "B", 0.6), ("B", "C", 0.6)]
    node_cost = {"A": 100.0, "B": 100.0, "C": 100.0}
    return nodes, edges, node_cost


@suite.case
def test_T3_baseline_reproducible_and_banded():
    from agent import risk_simulator as S
    nodes, edges, cost = _chain_fixture()
    seed_probs = {"A": 1.0, "B": 0.0, "C": 0.0}   # A always seeds
    a = S.simulate_plant_risk(nodes, edges, seed_probs, cost, trials=4000, seed=42)
    b = S.simulate_plant_risk(nodes, edges, seed_probs, cost, trials=4000, seed=42)
    assert a == b, "same seed must be byte-reproducible"
    # E[loss] = 100 + 100*0.6 + 100*0.36 = 196
    approx(a["mean_eml_usd"], 188.0, 204.0)
    assert a["trial_count"] == 4000 and a["seed"] == 42, a
    assert set(a["loss_contributions"]) == set(nodes), a["loss_contributions"]


@suite.case
def test_T3_suppression_monotonic_with_crn():
    from agent import risk_simulator as S
    nodes, edges, cost = _chain_fixture()
    seed_probs = {"A": 0.7, "B": 0.3, "C": 0.2}
    ranked = S.rank_interventions(
        nodes, edges, seed_probs, cost,
        candidates=[{"asset_id": n, "action": "repair_now",
                     "intervention_cost_usd": 0.0} for n in nodes],
        trials=4000, seed=42)
    # CRN guarantees suppressing a spontaneous seed never raises EML
    for r in ranked:
        assert r["gross_averted_eml_usd"] >= -1e-9, r


@suite.case
def test_T3_ranking_and_no_suppress_actions():
    from agent import risk_simulator as S
    nodes, edges, cost = _chain_fixture()
    seed_probs = {"A": 0.9, "B": 0.0, "C": 0.5}
    ranked = S.rank_interventions(
        nodes, edges, seed_probs, cost,
        candidates=[
            {"asset_id": "A", "action": "repair_now", "intervention_cost_usd": 5.0},
            {"asset_id": "C", "action": "repair_now", "intervention_cost_usd": 5.0},
            {"asset_id": "B", "action": "monitor", "intervention_cost_usd": 0.0},
        ],
        trials=4000, seed=42)
    # A drives the chain -> highest net averted; B is monitor -> exactly 0 averted
    assert ranked[0]["asset_id"] == "A", ranked
    b = [r for r in ranked if r["asset_id"] == "B"][0]
    assert b["gross_averted_eml_usd"] == 0.0, b


@suite.case
def test_T3_procurement_does_not_suppress_current_shift():
    from agent import risk_simulator as S
    nodes, edges, cost = _chain_fixture()
    ranked = S.rank_interventions(
        nodes, edges, {"A": 1.0, "B": 0.0, "C": 0.0}, cost,
        candidates=[{"asset_id": "A", "action": "procure_for_window",
                     "intervention_cost_usd": 0.0}],
        trials=1000, seed=42)
    p = ranked[0]
    assert p["gross_averted_eml_usd"] == 0.0, p
    assert p["net_averted_eml_usd"] == 0.0, p


@suite.case
def test_T3_cycle_terminates():
    from agent import risk_simulator as S
    nodes = ["X", "Y"]
    edges = [("X", "Y", 0.6), ("Y", "X", 0.6)]   # authored cycle
    out = S.simulate_plant_risk(nodes, edges, {"X": 0.5, "Y": 0.5},
                                {"X": 10.0, "Y": 10.0}, trials=200, seed=1)
    assert out["trial_count"] == 200, out   # must not hang


@suite.case
def test_T3_simulator_is_pure():
    import inspect
    from agent import risk_simulator as S
    src = inspect.getsource(S)
    for forbidden in ("import pandas", "read_csv", "agent.tools", "streamlit", "anthropic"):
        assert forbidden not in src, f"simulator core must not contain {forbidden!r}"


# ---- T4: tool layer + registries + feasibility ----------------------------
@suite.case
def test_T4_tools_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    for name in ("cost_tool", "risk_simulator_tool"):
        assert name in TOOL_FUNCS, f"{name} missing from TOOL_FUNCS"
        assert any(s["name"] == name for s in TOOL_SCHEMAS), f"{name} missing from TOOL_SCHEMAS"


@suite.case
def test_T4_cost_tool_shape_and_proxy():
    from agent.tools import cost_tool
    out = cost_tool("GEARBOX-05")
    ec = out["event_cost_proxy"]
    assert ec["label"] == "expected event-cost proxy", ec
    # per-event basis: never the raw historical total
    import config as C, pandas as pd
    dl = pd.read_csv(C.DELAY_LOGS_CSV)
    g = dl[dl.asset_id == "GEARBOX-05"]
    if len(g) > 0:
        assert ec["event_count"] == len(g), ec
        assert ec["downtime_min_per_event"] <= g["downtime_min"].sum(), "must divide by events"
    assert "feasibility" in out and "action" in out["feasibility"], out
    assert "emv" in out and "expected_value_preserved_usd" in out["emv"], out


@suite.case
def test_T4_mixed_stock_uses_job_primary_part():
    # GEARBOX-05 has PINION-G5 out of stock and OIL-VG320 in stock. The in-stock
    # oil must not make the pinion replacement job repairable.
    from agent.tools import cost_tool, prognostic_tool
    gb = cost_tool("GEARBOX-05")
    assert gb["planned_job"]["primary_part_no"] == "PINION-G5", gb
    assert gb["feasibility"]["action"] != "repair_now", gb["feasibility"]

    hv = cost_tool("HYD-VALVE-07")
    assert hv["planned_job"]["primary_part_no"] == "SPOOL-HV7", hv
    rul = prognostic_tool("HYD-VALVE-07")["rul_days"]
    expected = "procure_for_window" if 18 < rul else "monitor"
    assert hv["feasibility"]["action"] == expected, (rul, hv["feasibility"])


@suite.case
def test_T4_unresolved_primary_part_is_not_repairable():
    # LADLE-02 is a furnace-type asset but has no ELEC-CLMP1 inventory row. The
    # resolver must not substitute another asset's furnace part or longest-lead part.
    from agent.tools import cost_tool
    out = cost_tool("LADLE-02")
    assert out["primary_part_unresolved"] is True, out
    assert out["planned_job"]["primary_part_no"] is None, out["planned_job"]
    assert out["feasibility"]["action"] in {"monitor", "defer_capacity"}, out["feasibility"]


@suite.case
def test_T4_risk_simulator_tool_buckets_and_distribution():
    from agent.tools import risk_simulator_tool
    out = risk_simulator_tool()
    sim = out["simulation"]
    for k in ("mean_eml_usd", "p50_eml_usd", "p90_eml_usd", "p95_eml_usd",
              "trial_count", "seed"):
        assert k in sim, sim
    # no deferred-bucket asset may be prescribed repair_now
    procure_seen = False
    for p in out["prescriptions"]:
        if p.get("planner_bucket") == "deferred":
            assert p["action"] == "defer_capacity", p
        if p["action"] == "procure_for_window":
            procure_seen = True
            assert p["lead_time_days"] < p["predicted_rul_days"], p
            assert p["gross_averted_eml_usd"] == 0.0, p
            assert p["net_averted_eml_usd"] == 0.0, p
            assert p["value_at_risk_usd"] is not None, p
            assert "planned_action_cost_usd" in p, p
    assert procure_seen, "expected at least one procure_for_window candidate in demo data"


# ---- T5: five-block render carries dollars; structured parity --------------
@suite.case
def test_T5_five_blocks_present_and_dollars_in_1_and_4():
    from agent.orchestrator import run_deterministic
    res = run_deterministic("Status of GEARBOX-05?")
    text = res.answer_markdown
    for h in ("### 1.", "### 2.", "### 3.", "### 4.", "### 5."):
        assert h in text, f"missing block header {h}"
    block1 = text.split("### 2.")[0]
    block4 = text.split("### 4.")[1].split("### 5.")[0]
    assert "$" in block1, "Block 1 must carry the expected event-cost proxy in $"
    assert "$" in block4, "Block 4 must carry estimated financial exposure/value in $"


@suite.case
def test_T5_structured_has_cost_fields():
    from agent.orchestrator import run_deterministic
    res = run_deterministic("Status of GEARBOX-05?")
    assert "cost" in res.structured, res.structured.keys()
    assert "emv" in res.structured["cost"], res.structured["cost"]


@suite.case
def test_T5_structured_from_trace_parity():
    from agent.orchestrator import _structured_from_trace
    trace = [{"tool": "cost_tool", "input": {"asset_id": "GEARBOX-05"},
              "output": {"asset_id": "GEARBOX-05",
                         "emv": {"expected_value_preserved_usd": 123.0},
                         "event_cost_proxy": {"total_usd": 999.0}}}]
    s = _structured_from_trace(trace, "GEARBOX-05")
    assert s.get("cost", {}).get("emv", {}).get("expected_value_preserved_usd") == 123.0, s


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
