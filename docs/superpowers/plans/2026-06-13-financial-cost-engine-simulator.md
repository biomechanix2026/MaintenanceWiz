# Financial Cost Engine + Risk Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure direct-cost economics core and a seeded Independent-Cascade Monte-Carlo simulator, surfaced via `cost_tool` + `risk_simulator_tool`, that express plant risk as estimated value preserved by feasible repair-now actions and value at risk for procurement/monitoring actions.

**Architecture:** Two new pure cores (`agent/economics.py`, `agent/risk_simulator.py`) with no `agent.tools`/pandas/IO imports, composed by two thin tools in `agent/tools.py` and dispatched identically in both orchestrator modes. Cascade-cost composition and feasibility gating live in the tool layer; the cores take normalized inputs only. Dollars fold additively into the five-block render Blocks 1 & 4 and annotate planner/WO output without changing allocation order.

**Tech Stack:** Python, numpy (already a hard dep), pandas (tool layer only), the repo's zero-dependency `evals._harness` (no pytest).

**Spec:** `docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md`

---

## File structure

| File | Responsibility |
|------|----------------|
| `config.py` | New cost/sim constants (single source of truth) |
| `data/job_templates.csv` | New `primary_part_no` column |
| `data/generate_mock_data.py` | Emit `primary_part_no` deterministically |
| `agent/economics.py` | NEW - pure direct-cost primitives (no IO, no cascade) |
| `agent/risk_simulator.py` | NEW - pure Independent-Cascade Monte-Carlo with common random numbers |
| `agent/tools.py` | `cost_tool`, `risk_simulator_tool`; planner/WO `averted_usd` annotations |
| `agent/orchestrator.py` | Register both tools; dispatch `cost_tool`; structured parity both paths; render dollar lines |
| `agent/system_prompt.py` | Instruct LLM mode to use cost/sim tools, tool-grounded only |
| `app/streamlit_app.py` | Plant-risk panel |
| `scripts/pre_shift_run.py` | Value-preserved summary line |
| `scripts/build_demo_assets.py` | Exclude both tools from hosted demo |
| `evals/economics_sim_tests.py` | NEW - unit + feasibility tests for cores/tools |
| `evals/feature_tests.py` / `tool_contract_tests.py` | Registry + contract assertions |

Conventions to follow (verified in repo):
- Eval suites use `from evals._harness import Suite, run_suites` (plus `approx`, `sandbox`), `@suite.case` on `def test_<ID>():`, and end with `if __name__ == "__main__": raise SystemExit(run_suites(suite))`. No pytest.
- `prognostic_tool(asset_id)` returns `{"rul_days": float, "failure_probability_30d": float, ...}`.
- `agent.cascade.build_graph()` returns `{node: [downstream_nodes]}`; edge `u->v` means u's failure impacts v; it is a DAG. `agent.cascade.downstream(asset_id)` returns `[(node, hops)]`.
- `agent.planner.plan_shift(...)` returns `{"scheduled":[...], "deferred":[...], "procurement":[...], "capacity":{...}, "basis":str}`.
- `config.CASCADE_DECAY == 0.6`, `config.MAX_RUL_DAYS == 120`.

---

## Task 1: Config constants + job-template part mapping

**Files:**
- Modify: `config.py` (append a financial/sim block near `CASCADE_DECAY`, ~line 123)
- Modify: `data/job_templates.csv`
- Modify: `data/generate_mock_data.py` (job-template writer)
- Test: `evals/economics_sim_tests.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `evals/economics_sim_tests.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL on `config missing TONNAGE_MARGIN_USD_PER_TON` (and/or missing column).

- [ ] **Step 3: Add config constants**

Append to `config.py` after the `CASCADE_GAIN` line (~124):

```python
# --- Financial cost engine + risk simulator (DEMO ECONOMICS - not plant-sourced) ---
DOWNTIME_COST_USD_PER_HOUR = {     # $/hr of lost production by asset type
    "furnace": 120000, "conveyor": 18000, "pump": 22000, "valve": 16000,
    "mill": 90000, "gearbox": 65000, "compressor": 30000, "crane": 25000,
}
TONNAGE_MARGIN_USD_PER_TON = 75    # $/ton of lost/scrapped product margin
PLANNED_STOP_COST_FACTOR = 0.35    # planned stop costs this fraction of unplanned downtime $/hr
DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE = {   # fallback when an asset has no delay history
    "furnace": 90, "conveyor": 45, "pump": 40, "valve": 35,
    "mill": 120, "gearbox": 75, "compressor": 50, "crane": 30,
}
DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE = {
    "furnace": 60, "conveyor": 20, "pump": 15, "valve": 10,
    "mill": 80, "gearbox": 40, "compressor": 12, "crane": 8,
}
SIMULATION_TRIALS = 1000           # Monte-Carlo trials; target < 1s
SIMULATION_SEED = 42               # common-random-numbers base seed -> reproducible
CASCADE_EDGE_PROBABILITY_FLOOR = 0.05
CASCADE_EDGE_PROBABILITY_CAP = 0.85
```

- [ ] **Step 4: Add `primary_part_no` to the data and generator**

In `data/generate_mock_data.py`, find the dict/rows that build `job_templates.csv` (search
`job_templates` / `required_skill`). Add a `primary_part_no` to each row using this explicit
limiting-part mapping; do not infer from longest lead time or stock status:

```python
JOB_TEMPLATES = [
    # asset_type,  task,                                 est_hours, required_skill, primary_part_no
    ("furnace",    "Electrode clamp service",            4.0, "electrical", "ELEC-CLMP1"),
    ("conveyor",   "Drive bearing inspection/replace",   3.0, "mechanical", "BRG-6314"),
    ("pump",       "Mechanical seal service",            3.5, "mechanical", "SEAL-CART-12"),
    ("valve",      "Proportional valve spool service",   2.5, "hydraulic",  "SPOOL-HV7"),
    ("mill",       "Work roll change",                   5.0, "mechanical", "ROLL-WR4"),
    ("gearbox",    "Pinion inspection/replace",          4.0, "mechanical", "PINION-G5"),
    ("compressor", "Compressor service",                 3.0, "mechanical", "COMP-SVC09"),
    ("crane",      "Crane electrical inspection",        2.0, "electrical", "CRANE-CONT6"),
]
```

Add matching inventory rows for the two asset types that currently have a job template but no
primary part in `spare_parts_inventory.csv`:

```python
("COMP-SVC09",   "COMPRESSOR-09", "Compressor service kit",           2, 1, 10, 1150),
("CRANE-CONT6", "CRANE-06",      "Crane contactor inspection kit",   1, 1, 12, 780),
```

Then ensure the written CSV header is:

```text
asset_type,task,est_hours,required_skill,primary_part_no
```

Then regenerate data so the CSV on disk carries the column:

Run: `python data/generate_mock_data.py`

Then hand-verify (one line; do not leave any blank):
Run: `python -c "import pandas as pd,config as C;print(pd.read_csv(C.JOB_TEMPLATES_CSV)[['asset_type','primary_part_no']])"`
Expected: every row has a non-empty `primary_part_no` that exists in `spare_parts_inventory.csv`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m evals.economics_sim_tests`
Expected: `T1 PASS`.

- [ ] **Step 6: Commit**

```bash
git add config.py data/job_templates.csv data/generate_mock_data.py evals/economics_sim_tests.py
git commit -m "feat(economics): config cost/sim constants + job_templates primary_part_no"
```

---

## Task 2: `agent/economics.py` - pure direct-cost core

**Files:**
- Create: `agent/economics.py`
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `evals/economics_sim_tests.py` (before the `__main__` block):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.economics'`.

- [ ] **Step 3: Implement `agent/economics.py`**

```python
"""
Pure direct-cost economics primitives for Maintenance Wizard.

Computes per-event and per-action dollar primitives ONLY. No pandas, no file IO,
no RAG, no inventory lookup, and NO cascade composition - cascade cost is composed
by the caller (cost_tool / risk_simulator) which holds the graph. This keeps the
core individually testable with synthetic scalars.

Spec: docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md
"""
from __future__ import annotations


def direct_event_cost(*, asset_type: str,
                      downtime_min_per_event: float,
                      tonnage_lost_per_event: float,
                      downtime_cost_usd_per_hour: float,
                      tonnage_margin_usd_per_ton: float) -> dict:
    """Direct cost of ONE failure event. Inputs are PER-EVENT - callers must divide
    aggregate delay history by event count before calling. Labelled a proxy."""
    downtime_usd = (downtime_min_per_event / 60.0) * downtime_cost_usd_per_hour
    tonnage_usd = tonnage_lost_per_event * tonnage_margin_usd_per_ton
    total = downtime_usd + tonnage_usd
    return {
        "asset_type": asset_type,
        "downtime_usd": round(downtime_usd, 2),
        "tonnage_usd": round(tonnage_usd, 2),
        "total_usd": round(total, 2),
        "label": "expected event-cost proxy",
        "basis": {
            "downtime_min_per_event": downtime_min_per_event,
            "tonnage_lost_per_event": tonnage_lost_per_event,
            "downtime_cost_usd_per_hour": downtime_cost_usd_per_hour,
            "tonnage_margin_usd_per_ton": tonnage_margin_usd_per_ton,
        },
    }


def planned_action_cost(*, planned_hours: float,
                        downtime_cost_usd_per_hour: float,
                        planned_stop_cost_factor: float,
                        primary_part_unit_cost_usd: float) -> dict:
    """Cost of doing the planned job: a discounted planned stop plus the part."""
    planned_downtime_usd = planned_hours * downtime_cost_usd_per_hour * planned_stop_cost_factor
    part_usd = primary_part_unit_cost_usd
    return {
        "planned_downtime_usd": round(planned_downtime_usd, 2),
        "part_usd": round(part_usd, 2),
        "total_usd": round(planned_downtime_usd + part_usd, 2),
    }


def emv(*, p_failure: float, failure_cost_usd: float, action_cost_usd: float) -> dict:
    """Expected value preserved by acting now vs. running to failure."""
    expected_failure_loss = p_failure * failure_cost_usd
    value_preserved = expected_failure_loss - action_cost_usd
    if value_preserved > 0:
        rec = "positive_expected_value"
    elif action_cost_usd == 0:
        rec = "monitor"
    else:
        rec = "not_economic_on_30d_horizon"
    return {
        "expected_failure_loss_usd": round(expected_failure_loss, 2),
        "action_cost_usd": round(action_cost_usd, 2),
        "expected_value_preserved_usd": round(value_preserved, 2),
        "recommendation": rec,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m evals.economics_sim_tests`
Expected: `T2-*` cases PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/economics.py evals/economics_sim_tests.py
git commit -m "feat(economics): pure direct-cost core (direct_event_cost, planned_action_cost, emv)"
```

---

## Task 3: `agent/risk_simulator.py` - Independent-Cascade Monte-Carlo with common random numbers

**Files:**
- Create: `agent/risk_simulator.py`
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `evals/economics_sim_tests.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.risk_simulator'`.

- [ ] **Step 3: Implement `agent/risk_simulator.py`**

```python
"""
Pure seeded Independent-Cascade Monte-Carlo over a plant dependency graph.

No file IO, no pandas, no Streamlit/Anthropic/RAG. Accepts already-normalized
inputs (nodes, weighted edges, per-node spontaneous failure probs, per-node direct
event costs). Uses COMMON RANDOM NUMBERS so candidate suppression is a paired,
near-zero-variance comparison against baseline (monotone: suppressing a spontaneous
seed can only remove activations).

Edge weight is interpreted as a per-hop propagation probability, clamped to
[floor, cap]. Suppression zeroes a node's SPONTANEOUS seed only; the node remains
susceptible to upstream propagation.

Spec: docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md
"""
from __future__ import annotations
import numpy as np


def _topo(nodes: list[str], edges: list[tuple]) -> list[str]:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for u, v, _w in edges:
        adj[u].append(v)
        indeg[v] += 1
    q = [n for n in nodes if indeg[n] == 0]
    order: list[str] = []
    while q:
        n = q.pop(0)
        order.append(n)
        for v in adj[n]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(nodes):           # cycle guard: append remaining once
        order += [n for n in nodes if n not in set(order)]
    return order


def _prep(nodes, edges, edge_floor, edge_cap):
    order = _topo(nodes, edges)
    idx = {n: k for k, n in enumerate(order)}
    edge_p = (np.array([min(edge_cap, max(edge_floor, w)) for _, _, w in edges])
              if edges else np.zeros(0))
    incoming: dict[int, list[tuple[int, int]]] = {}
    for e, (u, v, _w) in enumerate(edges):
        incoming.setdefault(idx[v], []).append((e, idx[u]))
    return order, idx, incoming, edge_p


def _activations(order, idx, incoming, edge_p, seed_p, U_seed, U_edge):
    active = U_seed < seed_p                # (trials, n) spontaneous
    for v in order:                         # topo order: upstream finalized first
        i = idx[v]
        for e, ui in incoming.get(i, ()):
            active[:, i] |= active[:, ui] & (U_edge[:, e] < edge_p[e])
    return active


def _draws(order, edges, seed, trials):
    rng = np.random.default_rng(seed)
    U_seed = rng.random((trials, len(order)))
    U_edge = rng.random((trials, len(edges))) if edges else np.zeros((trials, 0))
    return U_seed, U_edge


def simulate_plant_risk(nodes, edges, seed_probs, node_cost, *, trials, seed,
                        edge_floor=0.05, edge_cap=0.85) -> dict:
    order, idx, incoming, edge_p = _prep(nodes, edges, edge_floor, edge_cap)
    U_seed, U_edge = _draws(order, edges, seed, trials)
    seed_p = np.array([seed_probs.get(n, 0.0) for n in order])
    cost = np.array([node_cost.get(n, 0.0) for n in order])
    active = _activations(order, idx, incoming, edge_p, seed_p, U_seed, U_edge)
    losses = active @ cost
    contrib = active.mean(axis=0) * cost
    contrib_map = {order[k]: round(float(contrib[k]), 2) for k in range(len(order))}
    top = sorted(
        ({"asset_id": order[k], "mean_loss_contribution_usd": round(float(contrib[k]), 2)}
         for k in range(len(order))),
        key=lambda r: r["mean_loss_contribution_usd"], reverse=True)[:5]
    return {
        "mean_eml_usd": round(float(losses.mean()), 2),
        "p50_eml_usd": round(float(np.percentile(losses, 50)), 2),
        "p90_eml_usd": round(float(np.percentile(losses, 90)), 2),
        "p95_eml_usd": round(float(np.percentile(losses, 95)), 2),
        "trial_count": int(trials),
        "seed": int(seed),
        "loss_contributions": contrib_map,
        "top_contributors": top,
    }


def rank_interventions(nodes, edges, seed_probs, node_cost, candidates, *,
                       trials, seed, edge_floor=0.05, edge_cap=0.85) -> list:
    """Each candidate: {asset_id, action, intervention_cost_usd, ...passthrough}.
    Only 'repair_now' suppresses spontaneous failure this shift. Actions
    'procure_for_window'/'monitor'/'defer_capacity' apply NO suppression
    (averted == 0); procurement value is reported as value-at-risk elsewhere."""
    order, idx, incoming, edge_p = _prep(nodes, edges, edge_floor, edge_cap)
    U_seed, U_edge = _draws(order, edges, seed, trials)     # common random numbers
    base_seed_p = np.array([seed_probs.get(n, 0.0) for n in order])
    cost = np.array([node_cost.get(n, 0.0) for n in order])
    base_active = _activations(order, idx, incoming, edge_p, base_seed_p, U_seed, U_edge)
    base_eml = float((base_active @ cost).mean())

    out = []
    for c in candidates:
        if c.get("action") != "repair_now" or c["asset_id"] not in idx:
            averted = 0.0
        else:
            sp = base_seed_p.copy()
            sp[idx[c["asset_id"]]] = 0.0                   # suppress spontaneous seed only
            act = _activations(order, idx, incoming, edge_p, sp, U_seed, U_edge)
            averted = base_eml - float((act @ cost).mean())
        net = averted - float(c.get("intervention_cost_usd", 0.0))
        out.append({**c,
                    "gross_averted_eml_usd": round(averted, 2),
                    "net_averted_eml_usd": round(net, 2)})
    out.sort(key=lambda r: r["net_averted_eml_usd"], reverse=True)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m evals.economics_sim_tests`
Expected: all `T3-*` PASS. If `test_T3_baseline_reproducible_and_banded` lands just outside the band, widen the `approx` bounds slightly (Monte-Carlo at 4000 trials), do not change the model.

- [ ] **Step 5: Commit**

```bash
git add agent/risk_simulator.py evals/economics_sim_tests.py
git commit -m "feat(simulator): Independent-Cascade Monte-Carlo core with common random numbers"
```

---

## Task 4: Thin tools `cost_tool` + `risk_simulator_tool` and registration

**Files:**
- Modify: `agent/tools.py` (add both tools; add a `_primary_part` helper)
- Modify: `agent/orchestrator.py` (`TOOL_FUNCS` + `TOOL_SCHEMAS`)
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `evals/economics_sim_tests.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL with `ImportError: cannot import name 'cost_tool'`.

- [ ] **Step 3: Implement the tools in `agent/tools.py`**

Add near the other tools (after `work_order_draft_tool`, before the orchestrator-only helpers). These compose existing tools/data and the two pure cores:

```python
# ==========================================================================
# TOOL 8: cost_tool (asset-scope financial exposure; folds into Blocks 1 & 4)
# ==========================================================================
def _primary_part(asset_id: str, asset_type: str) -> dict | None:
    """Resolve the limiting part for the asset's templated job via job_templates'
    primary_part_no, matched into this asset's own inventory rows by exact part_no.
    Never substitute a different physical part."""
    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    row = jt[jt.asset_type == asset_type]
    if row.empty or "primary_part_no" not in jt.columns:
        return {"unresolved": True, "primary_part_no": None,
                "reason": "no job template primary_part_no"}
    want_raw = row.iloc[0].get("primary_part_no")
    if pd.isna(want_raw) or not str(want_raw).strip():
        return {"unresolved": True, "primary_part_no": None,
                "reason": "blank job template primary_part_no"}
    want = str(want_raw).strip()
    inv = inventory_tool(asset_id).get("parts", [])
    match = next((p for p in inv if p["part_no"] == want), None)
    if match is None:
        return {"unresolved": True, "primary_part_no": want,
                "reason": "primary part not stocked for this asset; mapping unresolved"}
    return {**match, "unresolved": False, "primary_part_no": want}


def cost_tool(asset_id: str) -> dict:
    """Estimated expected event-cost proxy, feasible action, and EMV for one asset.
    All dollar figures derive from tool outputs + config economics (never invented)."""
    from agent import cascade, economics
    reg = _registry()
    row = reg[reg.asset_id == asset_id]
    if row.empty:
        return {"error": f"Unknown asset {asset_id}"}
    atype = row.iloc[0]["type"]

    # per-event proxy (divide aggregate delay history by event count; type default if none)
    dl = delay_history_tool(asset_id)
    events = dl.get("events", 0)
    if events > 0:
        dt_per = dl["total_downtime_min"] / events
        tn_per = dl["tonnage_lost"] / events
    else:
        dt_per = C.DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE.get(atype, 60)
        tn_per = C.DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE.get(atype, 20)

    rate = C.DOWNTIME_COST_USD_PER_HOUR.get(atype)
    if rate is None:
        return {"error": f"No DOWNTIME_COST_USD_PER_HOUR for type {atype}"}

    own = economics.direct_event_cost(
        asset_type=atype, downtime_min_per_event=dt_per, tonnage_lost_per_event=tn_per,
        downtime_cost_usd_per_hour=rate, tonnage_margin_usd_per_ton=C.TONNAGE_MARGIN_USD_PER_TON)

    # cascade-coupled failure cost (composition lives HERE, not in the pure core)
    failure_cost = own["total_usd"]
    for nid, hops in cascade.downstream(asset_id):
        nrow = reg[reg.asset_id == nid]
        if nrow.empty:
            continue
        ntype = nrow.iloc[0]["type"]
        nrate = C.DOWNTIME_COST_USD_PER_HOUR.get(ntype, rate)
        nd = economics.direct_event_cost(
            asset_type=ntype,
            downtime_min_per_event=C.DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE.get(ntype, 60),
            tonnage_lost_per_event=C.DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE.get(ntype, 20),
            downtime_cost_usd_per_hour=nrate,
            tonnage_margin_usd_per_ton=C.TONNAGE_MARGIN_USD_PER_TON)
        failure_cost += nd["total_usd"] * (C.CASCADE_DECAY ** hops)

    prog = prognostic_tool(asset_id)
    p_fail = prog.get("failure_probability_30d", 0.0)
    rul = prog.get("rul_days", C.MAX_RUL_DAYS)

    jt = pd.read_csv(C.JOB_TEMPLATES_CSV)
    trow = jt[jt.asset_type == atype]
    est_hours = float(trow.iloc[0]["est_hours"]) if not trow.empty else 3.0
    task = str(trow.iloc[0]["task"]) if not trow.empty else "Inspect asset"
    part = _primary_part(asset_id, atype)
    unresolved = bool(part and part.get("unresolved"))
    template_part_no = part.get("primary_part_no") if part else None
    part_no = None if unresolved else (part["part_no"] if part else None)
    part_cost = 0.0 if unresolved or not part else float(part["unit_cost_usd"])
    in_stock = bool(part and not unresolved and part["qty_on_hand"] > 0)
    lead = int(part["lead_time_days"]) if part and not unresolved else None

    # feasibility action (planner-bucket anchoring is applied in risk_simulator_tool)
    if unresolved:
        action, reason = "monitor", "primary part not stocked for this asset; mapping unresolved"
        act_cost = 0.0
    elif in_stock:
        action, reason = "repair_now", "primary part in stock"
        act_cost = economics.planned_action_cost(
            planned_hours=est_hours, downtime_cost_usd_per_hour=rate,
            planned_stop_cost_factor=C.PLANNED_STOP_COST_FACTOR,
            primary_part_unit_cost_usd=part_cost)["total_usd"]
    elif lead is not None and lead < rul:
        action, reason = "procure_for_window", "out of stock; normal lead within RUL"
        act_cost = economics.planned_action_cost(
            planned_hours=est_hours, downtime_cost_usd_per_hour=rate,
            planned_stop_cost_factor=C.PLANNED_STOP_COST_FACTOR,
            primary_part_unit_cost_usd=part_cost)["total_usd"]
    else:
        action, reason = "monitor", "primary part lead time exceeds predicted RUL"
        act_cost = 0.0

    val = economics.emv(p_failure=p_fail, failure_cost_usd=failure_cost, action_cost_usd=act_cost)
    return {
        "asset_id": asset_id,
        "event_cost_proxy": {
            "label": own["label"], "event_count": int(events),
            "downtime_min_per_event": round(dt_per, 1),
            "tonnage_lost_per_event": round(tn_per, 1),
            "total_usd": own["total_usd"],
        },
        "failure_cost_usd": round(failure_cost, 2),
        "primary_part_unresolved": unresolved,
        "planned_job": {"task": task, "primary_part_no": part_no,
                        "template_primary_part_no": template_part_no,
                        "est_hours": est_hours},
        "feasibility": {"action": action, "reason": reason,
                        "lead_time_days": lead, "predicted_rul_days": round(rul, 1),
                        "in_stock": in_stock},
        "emv": val,
    }


# ==========================================================================
# TOOL 9: risk_simulator_tool (plant-scope EML distribution + prescription)
# ==========================================================================
def risk_simulator_tool(trials: int | None = None) -> dict:
    """Seeded plant-risk distribution and feasible-action prescription, anchored to
    the next-shift planner's buckets so prescriptions are crew- and parts-feasible."""
    from agent import cascade, risk_simulator
    reg = _registry()
    g = cascade.build_graph()
    nodes = list(g.keys())
    edges = [(u, v, C.CASCADE_DECAY) for u, vs in g.items() for v in vs]

    seed_probs, node_cost, cost_by_asset = {}, {}, {}
    for nid in nodes:
        c = cost_tool(nid)
        if "error" in c:
            continue
        cost_by_asset[nid] = c
        node_cost[nid] = c["event_cost_proxy"]["total_usd"]
        seed_probs[nid] = prognostic_tool(nid).get("failure_probability_30d", 0.0)

    n_trials = int(trials or C.SIMULATION_TRIALS)
    sim = risk_simulator.simulate_plant_risk(
        nodes, edges, seed_probs, node_cost, trials=n_trials, seed=C.SIMULATION_SEED)
    loss_contrib = sim.get("loss_contributions", {})

    # planner buckets -> per-asset bucket label for feasibility anchoring
    plan = shift_plan_tool()
    bucket = {}
    for r in plan.get("scheduled", []):
        bucket[r["asset_id"]] = "scheduled"
    for r in plan.get("procurement", []):
        bucket[r["asset_id"]] = "procurement-monitor"
    for r in plan.get("deferred", []):
        bucket[r["asset_id"]] = "deferred"

    candidates = []
    for nid, c in cost_by_asset.items():
        b = bucket.get(nid)
        if b is None:
            continue                          # not flagged this shift
        feas = c["feasibility"]["action"]
        if b == "deferred":
            action = "defer_capacity"
        elif b == "scheduled" and feas == "repair_now":
            action = "repair_now"
        else:
            action = feas if feas in ("procure_for_window", "monitor") else "monitor"
        planned_action_cost = c["emv"]["action_cost_usd"]
        current_shift_cost = planned_action_cost if action == "repair_now" else 0.0
        candidates.append({
            "asset_id": nid, "planner_bucket": b, "action": action,
            "primary_part_no": c["planned_job"]["primary_part_no"],
            "primary_part_unresolved": c.get("primary_part_unresolved", False),
            "lead_time_days": c["feasibility"]["lead_time_days"],
            "predicted_rul_days": c["feasibility"]["predicted_rul_days"],
            "intervention_cost_usd": current_shift_cost,
            "planned_action_cost_usd": planned_action_cost,
            "value_at_risk_usd": loss_contrib.get(nid, 0.0),
        })

    ranked = risk_simulator.rank_interventions(
        nodes, edges, seed_probs, node_cost, candidates,
        trials=n_trials, seed=C.SIMULATION_SEED)
    return {"simulation": {k: sim[k] for k in
                           ("mean_eml_usd", "p50_eml_usd", "p90_eml_usd",
                            "p95_eml_usd", "trial_count", "seed")},
            "top_contributors": sim["top_contributors"],
            "prescriptions": ranked}
```

The new tool functions use local imports (`from agent import cascade, economics` inside
`cost_tool`; `from agent import cascade, risk_simulator` inside `risk_simulator_tool`) to match
the existing `cascade_tool` pattern and keep every referenced module in scope.

- [ ] **Step 4: Register both tools in `agent/orchestrator.py`**

In `TOOL_FUNCS` (after the `work_order_draft_tool` entry, ~line 44):

```python
    "cost_tool": lambda a: T.cost_tool(a["asset_id"]),
    "risk_simulator_tool": lambda a: T.risk_simulator_tool(a.get("trials")),
```

In `TOOL_SCHEMAS`, add two schema dicts matching the existing style:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m evals.economics_sim_tests`
Expected: all `T4-*` PASS. (If `risk_simulator_tool` is slow, lower `SIMULATION_TRIALS` is not needed - graph is small; it should be well under 1s.)

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py agent/orchestrator.py evals/economics_sim_tests.py
git commit -m "feat(tools): cost_tool + risk_simulator_tool, dual-registered, planner-anchored"
```

---

## Task 5: Orchestrator render + structured parity (Blocks 1 & 4, both modes)

**Files:**
- Modify: `agent/orchestrator.py` (`run_deterministic` dispatch, `_render`, `res.structured`, `_structured_from_trace`)
- Modify: `agent/system_prompt.py`
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `evals/economics_sim_tests.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL (`$` not in blocks / `cost` not in structured).

- [ ] **Step 3: Dispatch `cost_tool` and thread cost into render + structured**

In `run_deterministic` (around the STEP 1-4 gather, ~line 171-210), after the `cascade_tool` call, add:

```python
    cost = T.cost_tool(aid)
```

Pass `cost` into `_render(...)` (add a `cost` parameter to the `_render` signature at ~line 219 and to the call site) and include it in the structured result at ~line 210:

```python
    res.structured = {"asset_id": aid, "risk": risk, "cascade": casc, "prognostic": prog,
                      "cost": cost,
                      ...existing keys...}
```

In `_render(...)`, append to Block 1 (situation) where the asset state is described:

```python
    if cost and "error" not in cost:
        ec = cost["event_cost_proxy"]
        block1_lines.append(
            f"- Estimated exposure: ~${cost['failure_cost_usd']:,.0f} expected event-cost "
            f"proxy (cascade-coupled); single-event proxy ~${ec['total_usd']:,.0f}.")
```

and to Block 4 (recommendation):

```python
    if cost and "error" not in cost:
        v = cost["emv"]; f = cost["feasibility"]
        if f["action"] == "repair_now":
            block4_lines.append(
                f"- Estimated value preserved by repair_now: "
                f"~${v['expected_value_preserved_usd']:,.0f} "
                f"(expected run-to-failure loss ~${v['expected_failure_loss_usd']:,.0f}). "
                f"Counterfactual estimate under stated assumptions.")
        else:
            block4_lines.append(
                f"- Estimated value at risk pending {f['action']}: "
                f"~${v['expected_failure_loss_usd']:,.0f}; this is exposed risk, "
                f"not value preserved this shift.")
```

Adapt the exact variable names (`block1_lines`/`block4_lines`) to however `_render` accumulates each block - read the function and match its existing pattern; the requirement is one `$` line appended inside Block 1 and one inside Block 4, headers unchanged.

- [ ] **Step 4: Mirror cost into `_structured_from_trace`**

In `_structured_from_trace` (~line 320), add cost extraction from the trace:

```python
    cost = next((s["output"] for s in trace
                 if s.get("tool") == "cost_tool" and "error" not in s.get("output", {})), None)
    if cost is not None:
        out["cost"] = cost
```

(Match `out`/return-dict variable name used by the existing function.)

- [ ] **Step 5: Update the system prompt with a removable financial block**

In `agent/system_prompt.py`, add a delimited step block after `STEP 4.5 PLANT IMPACT` and
before `STEP 5 RECONCILE & OUTPUT`:

```text
STEP 4.7 FINANCIALS: for financial questions, call cost_tool (one asset) or
risk_simulator_tool (plant-wide). Report dollars ONLY from these tool outputs.
Say "estimated", "expected value preserved", "value at risk", and "percentile
bands"; never "exact", "proven", or "confidence bands".
```

Keep this as a distinct `STEP 4.7` block so the hosted demo builder can strip it when the
hosted tool surface excludes `cost_tool` and `risk_simulator_tool`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m evals.economics_sim_tests`
Expected: all `T5-*` PASS.

- [ ] **Step 7: Commit**

```bash
git add agent/orchestrator.py agent/system_prompt.py evals/economics_sim_tests.py
git commit -m "feat(orchestrator): dollars in Blocks 1&4 + structured parity (both modes)"
```

---

## Task 6: Planner + work-order dollar annotations (additive)

**Files:**
- Modify: `agent/tools.py` (`shift_plan_tool` annotation; `work_order_draft_tool` evidence)
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `evals/economics_sim_tests.py`:

```python
# ---- T6: planner/WO carry averted_usd without changing allocation ----------
@suite.case
def test_T6_planner_annotates_averted_usd():
    from agent.tools import shift_plan_tool
    plan = shift_plan_tool()
    for r in plan["scheduled"]:
        assert "averted_usd" in r, "scheduled rows must carry averted_usd"
    # allocation order/keys preserved (additive only)
    assert "basis" in plan and "capacity" in plan, plan.keys()


@suite.case
def test_T6_planner_sort_unchanged():
    # system_priority remains the primary sort key (annotation must not reorder)
    from agent.tools import shift_plan_tool
    plan = shift_plan_tool()
    sps = [r["system_priority"] for r in plan["scheduled"]]
    assert sps == sorted(sps, reverse=True), sps
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL (`averted_usd` absent).

- [ ] **Step 3: Annotate the planner output in `shift_plan_tool`**

In `shift_plan_tool` (`agent/tools.py`, ~line 502-529), after `plan = planner.plan_shift(...)`, annotate scheduled rows (do NOT re-sort, do NOT touch `planner.plan_shift`):

```python
    for r in plan.get("scheduled", []):
        c = cost_tool(r["asset_id"])
        r["averted_usd"] = (c["emv"]["expected_value_preserved_usd"]
                            if "error" not in c else None)
```

- [ ] **Step 4: Attach EMV evidence to drafted work orders**

In `work_order_draft_tool` (`agent/tools.py`, ~line 535-589), inside the per-job evidence dict (alongside `"spares"`, `"sop_citations"`), add:

```python
                "economics": cost_tool(aid).get("emv"),
```

(Use the loop's asset-id variable; match the existing evidence-dict indentation. Parts-blocked/deferred jobs already receive no draft WO - that invariant is untouched.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m evals.economics_sim_tests`
Expected: `T6-*` PASS.

- [ ] **Step 6: Run the full existing suite for regressions**

Run: `python -m evals.feature_tests`
Run: `python -m evals.judges`
Expected: existing planner/CMMS/cascade cases still PASS (allocation order and no-WO-for-parts-blocked unchanged).

- [ ] **Step 7: Commit**

```bash
git add agent/tools.py evals/economics_sim_tests.py
git commit -m "feat(tools): annotate planner + WO with averted_usd (allocation unchanged)"
```

---

## Task 7: Dashboard panel, pre-shift summary, hosted-demo exclusion

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `scripts/pre_shift_run.py`
- Modify: `scripts/build_demo_assets.py`
- Modify: `evals/demo_tests.py` for hosted exclusion contract
- Test: `evals/economics_sim_tests.py` (extend)

- [ ] **Step 1: Write the failing test (hosted exclusion + hosted prompt strip)**

Append to `evals/economics_sim_tests.py`:

```python
# ---- T7: hosted demo excludes the new tools --------------------------------
@suite.case
def test_T7_hosted_excludes_new_tools_and_prompt():
    import json, os, config as C
    from scripts.build_demo_assets import demo_tools, hosted_system_prompt, EXCLUDED_TOOLS

    assert {"cost_tool", "risk_simulator_tool"} <= EXCLUDED_TOOLS, EXCLUDED_TOOLS
    names = {t.get("name") for t in demo_tools()}
    assert "cost_tool" not in names, "hosted demo must exclude cost_tool"
    assert "risk_simulator_tool" not in names, "hosted demo must exclude risk_simulator_tool"

    hp = hosted_system_prompt()
    assert "cost_tool" not in hp, "hosted prompt must not order cost_tool"
    assert "risk_simulator_tool" not in hp, "hosted prompt must not order risk_simulator_tool"

    path = os.path.join(C.ROOT, "web", "data", "tools.json")
    if not os.path.exists(path):
        from evals._harness import gap
        gap("web/data/tools.json not generated in this environment")
    names = {t.get("name") for t in json.load(open(path, encoding="utf-8"))}
    assert "cost_tool" not in names, "hosted demo must exclude cost_tool"
    assert "risk_simulator_tool" not in names, "hosted demo must exclude risk_simulator_tool"
```

- [ ] **Step 2: Run test to verify it fails (or GAPs)**

Run: `python -m evals.economics_sim_tests`
Expected: FAIL because `EXCLUDED_TOOLS` and `hosted_system_prompt()` do not yet exclude the
new financial tools; GAP only for the generated `tools.json` file when absent locally.

- [ ] **Step 3: Exclude both tools from the hosted build and prompt**

In `scripts/build_demo_assets.py`, update the docstring, `EXCLUDED_TOOLS`, `DEMO_NOTE`, and
`hosted_system_prompt()`.

The exclusion set becomes:

```python
EXCLUDED_TOOLS = {"fault_mode_tool", "feedback_tool", "cascade_tool",
                  "shift_plan_tool", "work_order_draft_tool",
                  "cost_tool", "risk_simulator_tool"}
```

Update the top docstring to say:

```text
The hosted demo exposes 10 of the 17 tools. Excluded:
- fault_mode_tool        (needs the optional sklearn fault_model.pkl artifact)
- feedback_tool          (persists to CSV + reindexes; writes don't survive a
                          stateless serverless instance)
- cascade_tool           (reads config.py topology; the demo bundles no config.py)
- shift_plan_tool        (plant-wide scan over config + live tools; not snapshot-friendly)
- work_order_draft_tool  (composes shift_plan_tool + writes draft artifacts; out of scope for the demo)
- cost_tool              (local-only: reads config economics and composes live plant tools)
- risk_simulator_tool    (local-only: composes plant topology, planner buckets and live risk tools)
```

Update `DEMO_NOTE` so the local-only sentence includes `cost_tool` and
`risk_simulator_tool`.

Generalize the prompt stripping:

```python
LOCAL_ONLY_STEP_PREFIXES = ("STEP 4.5", "STEP 4.7")


def hosted_system_prompt() -> str:
    """SYSTEM_PROMPT with local-only pipeline steps stripped, plus DEMO_NOTE."""
    kept, skip = [], False
    for ln in SYSTEM_PROMPT.splitlines():
        stripped = ln.lstrip()
        if any(stripped.startswith(prefix) for prefix in LOCAL_ONLY_STEP_PREFIXES):
            skip = True
            continue
        if skip and stripped.startswith("STEP "):
            skip = False
        if skip:
            continue
        kept.append(ln)
    return "\n".join(kept) + DEMO_NOTE
```

Re-run the builder if the environment supports it:

Run: `python scripts/build_demo_assets.py` (skip if it requires network/keys; the exclusion-set edit is the binding change)

- [ ] **Step 4: Update `evals/demo_tests.py` hosted contract**

Before editing, read the current working-tree version of `evals/demo_tests.py` because it may
already contain unrelated uncommitted changes. Layer this exact contract update on top:

```python
assert EXCLUDED_TOOLS == {"fault_mode_tool", "feedback_tool", "cascade_tool",
                          "shift_plan_tool", "work_order_draft_tool",
                          "cost_tool", "risk_simulator_tool"}
assert names.isdisjoint(EXCLUDED_TOOLS)
assert len(tools) == len(TOOL_SCHEMAS) - len(EXCLUDED_TOOLS)  # 10 of 17
```

In the hosted prompt test, keep the existing `STEP 4.5` assertions and add:

```python
assert "STEP 4.7" not in hp, "STEP 4.7 financial block not stripped from hosted prompt"
assert "cost_tool" not in hp, "hosted prompt still mentions cost_tool"
assert "risk_simulator_tool" not in hp, "hosted prompt still mentions risk_simulator_tool"
```

- [ ] **Step 5: Add the Streamlit plant-risk panel**

In `app/streamlit_app.py`, locate the Plant Bottleneck view (search `cascade` / `shift_plan`). Add a panel that calls `risk_simulator_tool()` and renders, with a table fallback (no hard new dependency):

```python
    st.subheader("Plant-Risk Simulation (estimated expected monetary loss)")
    sim = risk_simulator_tool()
    s = sim["simulation"]
    st.caption(f"{s['trial_count']} seeded trials (seed {s['seed']}); percentile bands, "
               f"not confidence intervals.")
    st.write({"mean": f"${s['mean_eml_usd']:,.0f}", "p50": f"${s['p50_eml_usd']:,.0f}",
              "p90": f"${s['p90_eml_usd']:,.0f}", "p95": f"${s['p95_eml_usd']:,.0f}"})
    if sim["prescriptions"]:
        st.markdown("**Feasible actions (value preserved for repair; value at risk otherwise):**")
        st.dataframe(sim["prescriptions"])
```

(Match the file's existing import of `risk_simulator_tool` from `agent.tools`; add it to the existing tools import.)

- [ ] **Step 6: Add the pre-shift value-preserved / value-at-risk summary**

In `scripts/pre_shift_run.py`, where the briefing markdown is assembled, add:

```python
    sim = risk_simulator_tool()
    top = sim["prescriptions"][0] if sim["prescriptions"] else None
    lines.append(
        f"- Estimated plant exposure: mean ~${sim['simulation']['mean_eml_usd']:,.0f} "
        f"(p90 ~${sim['simulation']['p90_eml_usd']:,.0f}).")
    if top:
        if top["action"] == "repair_now":
            lines.append(
                f"- Top feasible action: **repair_now** on {top['asset_id']} "
                f"(~${top['net_averted_eml_usd']:,.0f} estimated value preserved).")
        else:
            lines.append(
                f"- Top feasible action: **{top['action']}** on {top['asset_id']} "
                f"(~${top['value_at_risk_usd']:,.0f} estimated value at risk pending action).")
```

(Match the briefing's existing line-accumulator variable and the `risk_simulator_tool` import.)

- [ ] **Step 7: Run tests + regressions**

Run: `python -m evals.economics_sim_tests`
Run: `python -m evals.tool_contract_tests`
Run: `python -m evals.demo_tests`
Expected: `T7` PASS (or GAP if no `tools.json`); existing contract/demo suites still PASS.

- [ ] **Step 8: Commit**

```bash
git add app/streamlit_app.py scripts/pre_shift_run.py scripts/build_demo_assets.py web/data/tools.json evals/economics_sim_tests.py evals/demo_tests.py
git commit -m "feat(ui): plant-risk panel + pre-shift value-preserved summary; exclude new tools from hosted demo"
```

---

## Task 8: Full regression sweep + register the new suite

**Files:**
- Modify: `evals/judges.py` or the suite aggregator (if suites are centrally listed)

- [ ] **Step 1: Wire the new suite into the aggregate run (if applicable)**

Check whether `evals/judges.py` (or a top-level runner) imports/aggregates the per-feature suites. If it does, add `economics_sim_tests`. If suites are run individually (as `feature_tests` is), no change is needed - document the run command in the suite docstring (already present).

- [ ] **Step 2: Run the full documented regression set**

```bash
python -m evals.judges
python -m evals.feature_tests
python -m evals.reporting_tests
python -m evals.tool_contract_tests
python -m evals.demo_tests
python -m evals.economics_sim_tests
```

Expected: 0 failures across all suites. Known GAPs are acceptable (e.g. missing `tools.json` locally). If `sklearn` is absent, regenerate the fallback model artifact (`python ml/train_model.py`) before treating prognostic failures as logic failures.

- [ ] **Step 3: Commit any aggregator change**

```bash
git add evals/judges.py
git commit -m "test: include economics/simulator suite in regression set"
```

---

## Self-review notes (author checklist, completed)

- **Spec coverage:** config constants (T1), job->part mapping (T1), pure economics direct-only (T2), simulator + CRN + repair-only suppression semantics + cycle guard (T3), both tools dual-registered (T4), feasibility gates + planner-bucket anchoring + parts-blocked->monitor (T4), Blocks 1&4 dollars + structured parity both paths (T5), planner/WO annotations without reordering (T6), dashboard + pre-shift + hosted exclusion + hosted prompt strip (T7), language discipline (T5 prompt + render strings). Causal ML/ledger correctly absent (non-goals).
- **Placeholder scan:** every code step shows real code; integration steps that depend on existing local variable names explicitly instruct "match the existing pattern" and state the binding requirement (e.g. one `$` line per block).
- **Type consistency:** `cost_tool` returns `event_cost_proxy`/`failure_cost_usd`/`primary_part_unresolved`/`feasibility`/`emv`; consumed with those exact keys in T4/T5/T6/T7 and in `risk_simulator_tool`. `rank_interventions` emits `net_averted_eml_usd`/`gross_averted_eml_usd`; `risk_simulator_tool` adds `planned_action_cost_usd` and `value_at_risk_usd` so non-repair rows are not labelled as value preserved. Simulator percentile keys `mean/p50/p90/p95_eml_usd` and `loss_contributions` are consistent across core, tool, dashboard, and pre-shift.
