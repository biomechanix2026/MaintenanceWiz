# Financial Cost Engine + Risk Simulator - Design Spec

Status: revised for review after correctness pass

Owner: Codex / Maintenance Wizard

Date: 2026-06-13

## Purpose

Extend Maintenance Wizard from constraint-aware prediction into defensible prescription by estimating the expected monetary value preserved by feasible next-shift actions.

The design stays inside the current architecture:

- deterministic mode remains the reproducible baseline;
- LLM mode remains a thin tool-use layer over the same tools;
- every user-facing recommendation still traces back to tool output;
- the current five-block output contract remains mandatory.

This is not a causal-ML implementation. It is the first production-shaped step toward prescriptive economics: deterministic direct-cost estimates, seeded plant-risk simulation, and evaluation hooks that can later support stronger counterfactual work.

## Design Decisions

### Locked Vocabulary

New modules:

- `agent/economics.py`
- `agent/risk_simulator.py`

New tools:

- `cost_tool`
- `risk_simulator_tool`

Avoid the earlier names `plant_risk_tool`, `simulator.py`, and `cost_of_failure`. The new names make the boundary clear: economics computes direct cost primitives; the simulator composes plant-wide risk.

### Job-To-Part Feasibility

`data/job_templates.csv` must gain a `primary_part_no` column.

This column encodes the limiting part consumed by each templated job. The current CSV has only:

```text
asset_type,task,est_hours,required_skill
```

The existing task strings imply the limiting parts, but the simulator must not infer feasibility from prose. Examples:

- gearbox pinion job -> `PINION-G5`
- hydraulic valve spool service -> `SPOOL-HV7`

The simulator's feasibility gate keys off the planned job's `primary_part_no`, not the worst out-of-stock part anywhere on the asset.

The existing `risk_score_tool.constraint_flag` behavior stays byte-stable for eval compatibility. Its current asset-level inventory check remains the broad risk flag. The simulator adds a more precise planned-job feasibility layer on top.

### Action Set

The prescription action vocabulary is:

- `repair_now`: planned job's primary part is in stock and the planner has scheduled the work.
- `procure_for_window`: primary part is out of stock, normal lead time is less than predicted RUL, and the planner places the asset in a procurement-monitor bucket.
- `monitor`: primary part lead time is greater than or equal to predicted RUL, so repair before likely failure is infeasible.
- `defer_capacity`: the planner has no crew window for the job; the simulator may report value at risk but must not recommend immediate repair.

There is no `expedite_part` action in this design. The data has normal lead time only; it does not contain expedited lead times or expedition costs. True expedition stays out of scope until those economics exist in the data.

### Event-Cost Proxy

The cost layer labels delay-derived financial values as an expected event-cost proxy.

For assets with delay history:

- `downtime_min_per_event = total_downtime_min / event_count`
- `tonnage_lost_per_event = total_tonnage_lost / event_count`

For assets without delay history, use asset-type defaults from `config.py`.

This is intentionally not described as a measured run-to-failure loss. It is a delay-event proxy derived from the available historical logs.

### Common Random Numbers

`risk_simulator.py` uses common random numbers across baseline and candidate evaluations.

For each simulation request, the core creates one deterministic set of random variates for:

- spontaneous seed failures;
- cascade edge activations;
- any per-trial ordering choices.

Every candidate action reuses those same variates. A candidate intervention overrides only the target asset's spontaneous seed failure draw. This makes `averted_eml_usd` a controlled comparison against the baseline rather than an artifact of independent Monte Carlo noise.

### Suppression Semantics

Suppressing an asset means:

- set the target asset's spontaneous seed failure probability to zero for that candidate run;
- keep the asset in the graph;
- allow it to be affected by upstream starvation, downstream backup, or other propagated impacts.

The simulator is therefore measuring the value of preventing the asset from initiating a failure, not pretending the asset is disconnected from the plant.

### Percentile Bands

Simulation output uses percentile terminology:

- `mean_eml_usd`
- `p50_eml_usd`
- `p90_eml_usd`
- `p95_eml_usd`
- `trial_count`
- `seed`

Do not call these confidence bands. They are distribution percentiles from seeded simulation trials.

### Planner-Bucket Anchor

`risk_simulator_tool` consumes `shift_plan_tool` output. It may rank prescriptions only inside planner-feasible buckets:

- `scheduled` rows can become `repair_now`;
- `procurement-monitor` rows can become `procure_for_window` or `monitor`;
- `deferred` rows can become `defer_capacity` only.

This prevents the simulator from recommending work that the deterministic planner has no hours, crew, or material path to execute.

## Non-Goals

- Do not add causal forests, doubly robust learners, or CATE estimation yet.
- Do not add expedition economics without new data fields.
- Do not claim mathematically proven self-accountability.
- Do not replace `risk_score_tool.constraint_flag`.
- Do not make Chroma, sklearn, shap, or any simulation dependency mandatory.
- Do not change the five-block output contract.

## Data Contract Changes

### `data/job_templates.csv`

Add:

```text
primary_part_no
```

Required behavior:

- every templated job must have a non-empty `primary_part_no`;
- every `primary_part_no` must resolve to at least one row in `data/spare_parts_inventory.csv`;
- data generation must emit the new column so regenerated demo data is stable;
- existing planner fields (`asset_type`, `task`, `est_hours`, `required_skill`) remain unchanged.

### `config.py`

Add economic and simulation constants as the single source of truth:

```python
TONNAGE_MARGIN_USD_PER_TON
PLANNED_STOP_COST_FACTOR
DEFAULT_EVENT_DOWNTIME_MIN_BY_TYPE
DEFAULT_EVENT_TONNAGE_LOST_BY_TYPE
SIMULATION_TRIALS
SIMULATION_SEED
CASCADE_EDGE_PROBABILITY_FLOOR
CASCADE_EDGE_PROBABILITY_CAP
```

Exact numeric defaults should be conservative and visibly labelled as demo economics.

## Economics Core

`agent/economics.py` is pure Python with no pandas dependency.

It computes direct event and action economics only. It does not query CSVs, run RAG, inspect inventory, or compute cascade cost.

Suggested functions:

```python
def direct_event_cost(
    *,
    asset_type: str,
    downtime_min_per_event: float,
    tonnage_lost_per_event: float,
    downtime_cost_usd_per_hour: float,
    tonnage_margin_usd_per_ton: float,
) -> dict:
    ...


def planned_action_cost(
    *,
    planned_hours: float,
    downtime_cost_usd_per_hour: float,
    planned_stop_cost_factor: float,
    primary_part_unit_cost_usd: float,
) -> dict:
    ...


def emv(
    *,
    p_failure: float,
    failure_cost_usd: float,
    action_cost_usd: float,
) -> dict:
    ...
```

`direct_event_cost` returns:

- downtime component;
- tonnage component;
- total expected event-cost proxy;
- input basis used.

`planned_action_cost` returns:

- planned downtime component;
- primary part component;
- total planned action cost.

`emv` returns:

- expected failure loss;
- action cost;
- expected value preserved.

The cascade layer may pass simulator-computed cascade cost into tool output, but that composition happens outside `agent/economics.py`.

## Risk Simulator Core

`agent/risk_simulator.py` is a deterministic, seeded Independent Cascade simulator over a plant dependency graph.

It accepts already-normalized inputs:

- nodes/assets;
- directed weighted dependency edges;
- per-node spontaneous failure probabilities;
- per-node direct event-cost proxies;
- planner buckets;
- candidate action feasibility;
- trial count;
- seed.

It returns:

- baseline expected monetary loss distribution;
- percentile bands;
- top loss contributors;
- feasible prescriptions ranked by `averted_eml_usd`;
- reproducibility metadata.

The core must be free of file IO, pandas, Streamlit, Anthropic, and RAG dependencies.

### Candidate Evaluation

For each candidate:

1. Reuse the baseline random variates.
2. Override only the candidate asset's spontaneous seed activation.
3. Leave all graph propagation behavior intact.
4. Compute candidate EML.
5. Report `averted_eml_usd = baseline_eml_usd - candidate_eml_usd`.

With common random numbers, preventing a spontaneous seed failure should never increase EML in the paired comparison, except for explicit modelling changes added later.

## Tool Layer

### `cost_tool(asset_id)`

Composes existing deterministic tools and CSV-backed data:

- asset metadata;
- prognostic risk;
- delay history;
- job template;
- primary part inventory;
- planner availability where already available;
- direct economics from `agent/economics.py`.

Returns:

```json
{
  "asset_id": "GEARBOX-05",
  "event_cost_proxy": {
    "label": "expected event-cost proxy",
    "event_count": 3,
    "downtime_min_per_event": 72.0,
    "tonnage_lost_per_event": 40.0,
    "total_usd": 12500.0
  },
  "planned_job": {
    "task": "Pinion inspection/replace",
    "primary_part_no": "PINION-G5",
    "required_skill": "mechanic",
    "est_hours": 4.0
  },
  "feasibility": {
    "action": "monitor",
    "reason": "primary part lead time exceeds predicted RUL",
    "lead_time_days": 45,
    "predicted_rul_hours": 18.5
  },
  "emv": {
    "expected_failure_loss_usd": 8400.0,
    "planned_action_cost_usd": 0.0,
    "expected_value_preserved_usd": 0.0
  }
}
```

Values above are illustrative only.

### `risk_simulator_tool(trials=None)`

Builds the simulator input from:

- asset registry;
- current prognostics;
- `cost_tool` outputs;
- plant dependency graph;
- `shift_plan_tool` output;
- configured simulation constants.

Returns:

```json
{
  "simulation": {
    "trial_count": 1000,
    "seed": 13,
    "mean_eml_usd": 54000.0,
    "p50_eml_usd": 12000.0,
    "p90_eml_usd": 130000.0,
    "p95_eml_usd": 180000.0
  },
  "top_contributors": [
    {
      "asset_id": "GEARBOX-05",
      "mean_loss_contribution_usd": 18000.0
    }
  ],
  "prescriptions": [
    {
      "asset_id": "HYD-VALVE-07",
      "planner_bucket": "procurement-monitor",
      "action": "procure_for_window",
      "primary_part_no": "SPOOL-HV7",
      "averted_eml_usd": 9200.0,
      "reason": "normal lead time is inside predicted RUL"
    }
  ]
}
```

Values above are illustrative only.

## Orchestrator Integration

Update both tool registries in `agent/orchestrator.py`:

- `TOOL_FUNCS`
- `TOOL_SCHEMAS`

Deterministic mode should call:

1. existing asset/prognostic/context tools;
2. `shift_plan_tool`;
3. `cost_tool`;
4. `risk_simulator_tool`;
5. `_render()`.

LLM mode gets the new tool schemas, but the prompt must continue to say tool outputs are the only source of truth.

Structured parity must be maintained in both paths:

- deterministic structured result;
- `_structured_from_trace` for LLM mode.

Do not let LLM mode expose cost/risk fields that deterministic mode cannot produce from the same trace.

## Rendering Contract

The five-block answer remains:

1. Situation
2. Evidence
3. Risk
4. Recommendation
5. Work Order / Plan

Add economics and simulation details inside existing blocks:

- Situation: include expected event-cost proxy where available.
- Evidence: include delay-event basis and primary part mapping.
- Risk: include direct expected loss and plant-wide EML percentile bands.
- Recommendation: include feasible action vocabulary only.
- Work Order / Plan: include `repair_now` work orders only when the planner scheduled the job and the primary part is in stock; include procurement/monitor plan rows for `procure_for_window` and `monitor`.

The renderer must not imply that a procurement or monitor row is an executable repair work order.

## Hosted Snapshot

The static hosted UI remains a demo snapshot. It should not expose live `cost_tool` or `risk_simulator_tool` controls unless a matching API exists.

`web/data/tools.json` should either omit the new tools or label them as local-runtime only.

## Evaluation Plan

Run `python -m evals.judges` after implementation.

Add focused deterministic evals for:

- `job_templates.csv` includes `primary_part_no`;
- every `primary_part_no` resolves in inventory;
- mixed-stock assets use the job's primary part, not any out-of-stock part on the asset;
- `risk_score_tool.constraint_flag` output remains unchanged for existing scenarios;
- event-cost proxy divides historical totals by event count;
- no-history assets use configured asset-type defaults;
- `agent/economics.py` has no file IO and no cascade calculation;
- simulation output is reproducible for the same seed;
- common random numbers make paired suppression monotonic for seed-failure prevention;
- suppressed assets can still receive propagated upstream/downstream impacts;
- `risk_simulator_tool` cannot recommend `repair_now` for deferred rows;
- `procure_for_window` appears only when normal lead time is less than predicted RUL;
- LLM `_structured_from_trace` includes the same cost/risk fields as deterministic output;
- hosted tool metadata does not advertise unavailable live simulation controls.

## Expected Files Touched During Implementation

- `config.py`
- `data/job_templates.csv`
- `data/generate_mock_data.py`
- `agent/economics.py`
- `agent/risk_simulator.py`
- `agent/tools.py`
- `agent/orchestrator.py`
- `agent/system_prompt.py`
- `app/streamlit_app.py`
- `scripts/pre_shift_run.py`
- `scripts/build_demo_assets.py`
- `web/api/_core.py`
- `web/data/tools.json`
- `evals/judges.py`

## Resolved Decisions (were open questions)

1. **`primary_part_no` is one part per job (single limiting part).** Feasibility only
   needs the limiting part. The resolver should tolerate a future list, but the data
   model and logic ship single-part. A multi-part bill of materials is deferred because
   no current scenario needs it.
2. **`procure_for_window` creates a procurement-monitor plan row only.** It does NOT
   reserve future crew hours. `shift_plan_tool` allocation stays byte-stable and the
   planner judges remain untouched this tranche. Crew reservation against a part ETA is a
   separate, later planner change.
3. **The plant dependency graph stays config-owned, consumed via
   `cascade.build_graph()`.** `agent/cascade.py` already reads the config topology spec;
   the simulator consumes the same graph. No parallel topology, no drift from the cascade
   tool, no new tuning surface. Generating edges from asset metadata is rejected unless
   the cascade tool's own source is moved too.
