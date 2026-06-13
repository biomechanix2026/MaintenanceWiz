# UI Handoff — Cascade + Next-Shift Planner Dashboard Surfaces

**Intended target branch:** TBD — likely `codex/mw2-port` (the frontend rewrite). Confirm before applying.
**Why a handoff:** the backend (cascade + planner) shipped on `codex/plant-cascade`, but `app/streamlit_app.py`
was hands-off during the frontend rewrite. These are the deferred UI surfaces; the backend tools they
need (`cascade_tool`, `shift_plan_tool`, `agent.cascade.build_graph`) are all merged — no backend work remains.

When these land, delete the `🔜` tags on T4 steps 4–5 in `docs/UX_JOURNEYS.md`.

All snippets below are written against the *current* `app/streamlit_app.py`; re-anchor them to the
rewritten frontend's equivalents (the plant board, the asset deep-dive, and Tab 1).

## 1. Plant board (Tab 1) — system-priority columns + topology graph
- In `plant_scan()`, after the abnormality call add `casc = cascade_tool(a["asset_id"])` and two row
  keys: `"system_priority": casc["system_priority"]`, `"downstream_n": casc["downstream_count"]`.
  **Keep the existing `priority_score` ranking** (additive); show `system_priority` alongside.
- Add a topology graph via `st.graphviz_chart(dot)` from a DOT **string** built from
  `agent.cascade.build_graph()` (client-side render — no python `graphviz` dependency). Color nodes by
  priority band; wrap in `try/except` → fall back to the table / `data/plant_topology.json`.

## 2. Plant board (Tab 1) — "Next shift plan" panel
- Call `T.shift_plan_tool()` and render three lists + a utilisation line:
  - **Scheduled:** `asset_id — task → crew_id (est_hours, sys priority)`.
  - **Deferred (capacity):** `asset_id — reason` (the "no <skill> crew has …h free" strings).
  - **Procurement / monitored degradation:** `asset_id — reason` (the constraint flag).
  - Caption: per-skill utilisation from `capacity["by_skill"]`.
- This mirrors the `scripts/pre_shift_run.py` "Next shift plan" section — reuse its formatting.

## 3. Asset deep-dive (Tab 2) — downstream blast-radius panel
- `casc = cascade_tool(aid)`; if `downstream_count` show a caption
  (`system priority X/100 (own + cascade)`) and `st.dataframe(pd.DataFrame(casc["downstream"]))`;
  else "Terminal asset — no downstream dependents."

## Not in this handoff (separate deferred tranche)
The Workbook→`scenario_tool` what-if and the KPI panel belong to
`docs/superpowers/plans/2026-06-13-explain-and-manage-followup.md`, not here.

## Verification after wiring
`streamlit run app/streamlit_app.py` — Tab 1 shows System Priority / Downstream columns, the topology
graph, and the Next-shift-plan panel; Tab 2 (GEARBOX-05) shows the 2-row downstream table; Tab 2
(ROLL-MILL-11) shows "Terminal asset". The backend test battery is unaffected by UI code.
