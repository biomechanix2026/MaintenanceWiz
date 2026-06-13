# Next-Shift Planner MVP — Phase B

**Status:** Implemented on `codex/plant-cascade`.
**Depends on:** Phase A cascade (`2026-06-12-cascade-system-priority.md`) — the planner consumes
`system_priority`. **Replaces** the deferred `scenario_tool` + `kpi_summary` as the second feature of
this tranche (those are now `2026-06-13-explain-and-manage-followup.md`).

## Why
Cascade tells you *what matters most*; it does not resolve the actual constraint of maintenance ops:
**more flagged work than crew-hours.** The planner is the first feature that makes the wizard
*operate* — it turns the ranked board into an allocated next-shift plan.

## What was built
### Data contracts (`data/generate_mock_data.py`, hard-coded — no `random`, so existing CSVs stay byte-identical)
- **`data/crew_roster.csv`** — `crew_id,name,skill,shift_hours`. Two mechanical crews (16 h),
  one hydraulic (8 h), one electrical (8 h). Tight capacity → realistic contention.
- **`data/job_templates.csv`** — `asset_type,task,est_hours,required_skill`, one row per asset type.
- **`config.py`** — `CREW_ROSTER_CSV`, `JOB_TEMPLATES_CSV` paths.

### Pure core (`agent/planner.py`, no `agent.tools` import)
`plan_shift(candidates, crew, templates)`:
- `candidates`: `{asset_id, asset_type, system_priority, rul_days, criticality, priority_band, constraint_flag}`.
- **Per-crew** remaining-hour tracking (not a per-skill aggregate pool — a 5 h job needs one crew with
  5 h free even if two 3 h crews look sufficient).
- Rank by `(-system_priority, rul_days, -criticality)` → upstream bottleneck outranks isolated asset.
- `constraint_flag` set → **procurement + monitored degradation** (no crew hours). Feasible & a crew of
  the skill has room → **scheduled** (best-fit crew). Feasible but no single crew fits → **deferred**
  with reason. Returns `scheduled / deferred / procurement / capacity{by_crew,by_skill}`.
- Invariant: **no crew is allocated beyond its own `shift_hours`.**

### Tool + surface
- **`agent/tools.py` `shift_plan_tool()`** — plant-scope; scans the registry, filters flagged work
  (band HIGH/CRITICAL **or** `constraint_flag` **or** abnormal), enriches with `system_priority` /
  `criticality`, runs `plan_shift`. Dual-registered; **not** in the single-asset five-block pipeline
  (on-demand, like `fault_mode_tool`); **excluded from the hosted demo**.
- **`scripts/pre_shift_run.py`** — `action_queue` now also includes constraint-only assets; the
  briefing ends with a **"Next shift plan"** section (scheduled / deferred / procurement + utilisation).

## Tests
`evals/feature_tests.py` P1 (cascade pays off), P2 (infeasible part → procurement),
P3 (crew-hour limit → deferral with reason), P4 (dual registry), P5 (no crew overbooked, incl. the
aggregate-OK-but-single-crew-insufficient case). `evals/reporting_tests.py` OUT15 asserts the plan section.

## Representative output
PUMP-12 (utility, cascade-boosted) ranks #1; GEARBOX-05 (45 d pinion lead vs RUL) → procurement, not
scheduled; lower-priority mechanical jobs deferred as the two mechanical crews saturate (~14.5/16 h).

## Deferred to the UI handoff
Tab 1 "Next shift plan" panel — `docs/handoffs/cascade-ui-followup.md`.
