# Explain & Manage — Deferred Follow-up Tranche

**Status:** Deferred (not started). Split out of `2026-06-12-cascade-scenario-kpi.md` (Tasks 5–8).

## Why deferred
After the architecture review, the cascade tranche was narrowed to `cascade + next-shift planner MVP`
— the features that make the system *operate*. `scenario_tool` and `kpi_summary` mostly **explain or
summarize** decisions; valuable, but lower-leverage than the planner. They wait for their own tranche.

## Scope (when picked up)
- **`scenario_tool(asset_id, sensor_overrides, delay_days)`** — what-if projection of RUL, failure
  probability, priority band, abnormality status and the spares constraint, by pure recomputation
  through the existing verified components (RULModel, NOMINAL z-bands, RISK_WEIGHTS). On-demand
  evidence (not in the deterministic pipeline). Full code: `2026-06-12-cascade-scenario-kpi.md` Task 5.
  UI Workbook integration: that doc's Task 6.
- **`kpi_summary()`** — SQL-evidenced plant KPIs (MTTR/MTBF proxies, stockout risk, repeat failure
  modes) where every card/table carries its SQL. Unregistered UI helper. Full code: Task 7; Tab 1 KPI
  panel: Task 8.

## Notes for the implementer
- Tool count would go 14 → 15 (`scenario_tool` registered; `kpi_summary` stays unregistered).
- Decide hosted-demo behaviour: `scenario_tool` needs the live RUL model the snapshot avoids → likely
  **exclude** (add to `EXCLUDED_TOOLS`, bump the "10 of N" wording, update `evals/demo_tests.py`).
- Honour the same invariants: dual registry, five-block contract, `priority_score`/`RISK_WEIGHTS`
  untouched, pure-core + thin-tool, generator determinism.
