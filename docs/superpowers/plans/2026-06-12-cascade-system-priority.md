# Cascade / System Priority — Phase A

**Status:** Implemented on `codex/plant-cascade`.
**Supersedes:** the cascade half (Tasks 1–4) of `2026-06-12-cascade-scenario-kpi.md`, split out so
this tranche is `cascade + next-shift planner MVP` (see `2026-06-13-next-shift-planner-mvp.md`).
The deferred `scenario_tool` + `kpi_summary` live in `2026-06-13-explain-and-manage-followup.md`.
Design spec: `docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`.

## Goal
Move from per-asset risk to plant-level bottleneck reasoning. Add an asset-interdependency graph and a
derived **`system_priority`** that escalates upstream choke points — **additive and eval-safe**:
`risk_score_tool`, `RISK_WEIGHTS`, `priority_score` are never modified, so the existing judges hold.

## What was built
- **`config.py`** — `LINE_FLOW`, `LINE_ASSET_ORDER`, `UTILITY_EDGES`, `CASCADE_DECAY=0.6`, `CASCADE_GAIN=3.0`.
- **`agent/cascade.py`** (pure, no `agent.tools` import) — `build_graph()` (hybrid: intra-line serial
  chains + consecutive-line bridges + authored utility edges), `downstream()` (BFS, cycle-guarded),
  `blast_radius()` = `Σ criticality(d)·DECAY^hops(d)`.
- **`agent/tools.py` `cascade_tool(asset_id)`** — composes own priority with blast radius:
  `system_priority = min(100, own + CASCADE_GAIN·blast)`; unknown asset → error dict. Dual-registered.
- **`agent/orchestrator.py`** — `cascade_tool` dispatched in `run_deterministic` after `risk_score_tool`;
  Block 1 gains a "System impact" line, Block 5 a "Cascade path" line; `_structured_from_trace` parity.
- **`agent/system_prompt.py`** — STEP 4.5 PLANT IMPACT (tool-backed; stripped from the hosted prompt).
- **`data/generate_mock_data.py`** — dumps inspect-only `data/plant_topology.json`.

## Verified behaviour
`GEARBOX-05` blast = `5·0.6 + 4·0.6² = 4.44`; downstream `[ROLL-MILL-04, ROLL-MILL-11]`;
`system_priority ≥ priority_score`. `ROLL-MILL-11` (leaf) → blast 0, terminal.

## Tests
`evals/feature_tests.py` C1–C4; `evals/judges.py` `gearbox-cascade-impact` + `leaf-asset-terminal`
(4→6 cases); `evals/reporting_tests.py` OUT08 hardened to assert real plant-level escalation.

## Deferred to the UI handoff
Streamlit topology graph, `system_priority`/`downstream` columns, Tab 2 downstream panel —
`docs/handoffs/cascade-ui-followup.md` (frontend rewrite in flight on `codex/mw2-port`).
