# CMMS / Work-Order MVP

**Status:** Implemented on `codex/cmms-work-orders` (branched off `main` after the cascade +
next-shift-planner tranche landed).
**Depends on:** `shift_plan_tool`, `cascade_tool`, `risk_score_tool`, `inventory_tool`, `rag_tool`.

## Why
The planner now says *what should run this shift*. This is the first **system-of-action write-back**:
it turns each scheduled job into a trace-backed **draft work order** — the bridge from
decision-support toward an operating CMMS loop.

## What was built
- **`agent/tools.py` `work_order_draft_tool(persist=False, out_dir=None)`** — composes
  `shift_plan_tool` and, for each **scheduled** job, attaches evidence: `risk` (score/band/constraint/
  components), `cascade` (system_priority/blast/path), `spares` (per-part status/lead), `sop_citations`
  (manual sources via `rag_tool`), plus `crew_id` + `planned_hours`. Dual-registered; plant-scope,
  on-demand (not in the five-block pipeline); **excluded from the hosted demo**.
- **Approval-gated:** every WO is `status: "DRAFT"` with `approval.required=True, approved=False`.
  No autonomous closure. **Parts-infeasible / deferred jobs get NO work order** — they remain
  procurement / monitored-degradation actions.
- **Opt-in persistence (alert-style):** `persist=False` is side-effect-free; `persist=True` writes one
  JSON per WO to `reports/work_orders/` (config `WORK_ORDERS_DIR`). `out_dir` overrides the target
  (used by pre-shift + tests for isolation).
- **`scripts/pre_shift_run.py`** — the autonomous run now drafts WOs (`persist=True`) and adds a
  "Drafted work orders (CMMS)" section.

## Tests (`evals/feature_tests.py`)
- **W1:** one WO per scheduled job; WO assets == scheduled assets; disjoint from procurement+deferred;
  GEARBOX-05 (procurement-blocked) never gets a WO.
- **W2:** every WO carries risk/cascade/spares/SOP evidence + crew + hours, `status=DRAFT`, approval gate.
- **W3:** `persist=False` writes nothing; `persist=True` writes one JSON per WO.
- **W4:** dual registry. Plus `reporting_tests` OUT15 asserts the pre-shift CMMS section.

## Invariants honoured
Dual registry; `priority_score`/`RISK_WEIGHTS` untouched; pure-ish composition over verified tools;
opt-in side effects; hosted-demo surface reconciled (15 registered tools, 10 exposed).

## Deferred / next
- WO lifecycle (approve → assign → close) and a real CMMS adapter (this is a mock JSON write-back).
- `scenario_tool` + `kpi_summary` ("explain & manage" tranche) remain after this.
