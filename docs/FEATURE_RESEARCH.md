# Maintenance Wizard — Feature Research (repo-grounded)

> **Date:** 2026-06-13
> **Scope:** Feature direction for *this* repo — every recommendation below is mapped to existing code, specs, or data contracts, not a generic CMMS checklist.
> **Companions:** `docs/ARCHITECTURE_DESIGN.md` (harness & invariants), `docs/UIUX_SPEC.md` (surfaces & personas), `docs/UX_JOURNEYS.md` (today/to-be scenarios), `docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md` (cascade spec), `docs/superpowers/plans/2026-06-11-mw2-port.md` (landed MW2 port record), `docs/superpowers/plans/2026-06-12-cascade-system-priority.md` (cascade implementation record), `docs/superpowers/plans/2026-06-13-next-shift-planner-mvp.md` (planner MVP implementation record), `docs/superpowers/plans/2026-06-13-explain-and-manage-followup.md` (deferred scenario/KPI tranche).

---

## 1. Market direction (June 2026) → where this repo already stands

Strong maintenance platforms are converging on four themes. The repo's position against each:

| # | Market theme | Proxy | Repo position today |
|---|---|---|---|
| 1 | Mobile work execution (WOs, PMs, checklists, QR, meters, inventory) | [UpKeep features](https://upkeep.com/features/) | **Weakest axis.** UI/UX spec designs glove-first surfaces and an isolation checklist, but v1 is desktop Streamlit; no QR, offline, or photo capture. |
| 2 | AI-assisted EAM/APM (AI-prioritized work, CBM, visual inspection, inventory optimization, HSE) | [IBM Maximo](https://www.ibm.com/products/maximo) | **Strong on prioritization/CBM** (`risk_score_tool`, dual detectors, constraint flip); nothing on visual inspection; HSE is a single closure checklist. |
| 3 | Connected planning & scheduling (backlogs, skills, costs, parts replenishment) | [Oracle Maintenance](https://www.oracle.com/scm/maintenance/) | **Partial, improved by the planner MVP.** `pre_shift_run` now produces an allocated next-shift plan using crew/job-template contracts; no shift windows, permits, backlog work orders, costs, or replenishment write-back yet. |
| 4 | Evidence-grounded, governed AI (fused sources, deterministic verification) | [arXiv:2603.08171](https://arxiv.org/abs/2603.08171), [arXiv:2401.07871](https://arxiv.org/abs/2401.07871) | **The repo's identity and now stronger after MW2.** Five-block contract, trace, SQL echo, deterministic baseline, eval judges, hybrid BM25+RRF retrieval, LLM citations/prompt caching, `fault_mode_tool`, and C-MAPSS benchmark provenance. |

**Product angle confirmed by the codebase:** not "another CMMS," but a *maintenance command system* that converts sensor risk, SOP evidence, spares constraints, and production impact into an executable shift plan. Everything below serves that sentence.

---

## 2. Current baseline this research sequences from

The MW2 port has landed in the repo. Treat `docs/superpowers/plans/2026-06-11-mw2-port.md` as the implementation record, not queued work: `knowledge/rag.py` now has stdlib BM25 plus RRF hybrid retrieval, `agent/orchestrator.py` carries citable Anthropic document blocks and prompt caching, `agent/tools.py` exposes `fault_mode_tool`, `ml/cmapss.py` and `ml/benchmark_rul.py` provide the C-MAPSS benchmark path, and `evals/port_tests.py` guards the port.

That changes the priority stack. The evidence-grounding theme is no longer the next bet; it is the baseline other features should reuse. Two useful precedents are now available: on-demand evidence tools can degrade with `available: False`, and reliability work can use the AI4I failure-mode vocabulary (`TWF`, `HDF`, `PWF`, `OSF`, `RNF`) instead of inventing a new taxonomy.

The cascade/scenario/KPI bundle has been split after architecture review. The operating-process tranche is now `docs/superpowers/plans/2026-06-12-cascade-system-priority.md` + `docs/superpowers/plans/2026-06-13-next-shift-planner-mvp.md`: cascade produces `system_priority`, and `shift_plan_tool` consumes it to allocate the next shift under crew-hour and spares constraints. `scenario_tool` and `kpi_summary` are deferred to `docs/superpowers/plans/2026-06-13-explain-and-manage-followup.md` because they explain and summarize decisions rather than operating the maintenance process.

`docs/UX_JOURNEYS.md` adds the second planning lens: Part 1 proves the current app through four demo journeys; Part 2 proposes two to-be journeys (F1 manager "one inbox" and F2 technician "wrench doesn't stop for paperwork") with explicit gap tables. The NEW items from those tables are folded into §3 below.

---

## 3. Feature priorities, grounded

Ordered by (demo value × seed maturity) ÷ effort. Effort: S < 1 day, M = days, L = week+ for this codebase's conventions (tool + dual registry + deterministic dispatch + eval case + UI).

**Top recommendation:** land the **Cascade + Next-Shift Planner MVP** tranche as the next merge. Cascade upgrades the unit of reasoning from asset to plant; the planner is the first feature that turns that signal into an allocated operating plan. The backend is implemented on `codex/plant-cascade`; the remaining acceptance blocker is the UI handoff (`docs/handoffs/cascade-ui-followup.md`) so managers can see `system_priority`, blast radius, and the next-shift plan in the app.

### 3.1 Plant Cascade / Blast-Radius Prioritization — backend complete; UI pending (M)

- **Seeds:** complete design spec (`docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`) plus the split implementation record (`docs/superpowers/plans/2026-06-12-cascade-system-priority.md`); the pitch deck already advertises `cascade_tool` as roadmap.
- **Built:** topology in `config.py` (`LINE_FLOW`, `UTILITY_EDGES`, `CASCADE_DECAY/GAIN`) → pure `agent/cascade.py` → `cascade_tool` in both registries → Block 1 "System impact" line + Block 5 cascade path → cascade eval cases.
- **UI handoff:** `docs/handoffs/cascade-ui-followup.md` adds `system_priority`/`downstream_count` columns, topology graph, and a Tab 2 downstream panel.
- **Why first:** it upgrades the system's unit of reasoning from *asset* to *plant* — the supervisor persona's actual question — without disturbing the existing risk-score baseline (`system_priority` is additive; `priority_score`, `RISK_WEIGHTS`, and existing judges remain intact).

### 3.2 Next-Shift Planner MVP — backend complete; UI pending (M)

- **Seeds:** `pre_shift_run` already scanned the plant and built an action queue; cascade now supplies `system_priority`; the new `crew_roster.csv` and `job_templates.csv` contracts supply deterministic crew capacity and typical job effort.
- **Built:** pure `agent/planner.py` + `shift_plan_tool` allocate scheduled work, procurement/monitored-degradation actions, and deferrals with reasons under per-crew hour limits and spares constraints. `scripts/pre_shift_run.py` now appends a "Next shift plan" section.
- **Why now:** this is the first operating-process feature. It converts "these assets are risky" into "this is what the next shift should run, what cannot be fixed because parts cannot arrive, and what must defer because crew-hours are exhausted."
- **UI handoff:** surface the same plan in Tab 1 so Shalini sees scheduled, deferred, and procurement buckets without reading the markdown report.

### 3.3 Scenario Simulation / "lightweight digital twin" — deferred explain/manage follow-up (S–M)

- **Seeds:** the Deep-Dive "Workbook" expander (`app/streamlit_app.py` ~line 154) already perturbs the five sensor readings ±50% and recomputes RUL via `model.predict_rul`. All other component math (abnormality z-scores, risk weights, constraint comparison) exists as pure functions.
- **Build:** `scenario_tool(asset_id, sensor_overrides, delay_days)` composing existing tool internals → recomputed RUL, abnormality status, priority band, constraint flag, and (after §3.1) `system_priority`. Register in both registries, but keep it on-demand rather than in the deterministic five-block pipeline; host it in the existing Workbook expander; quick-chips in chat ("what if we wait 48 h?").
- **Direction match:** digital-twin literature ([arXiv:2509.24443](https://arxiv.org/abs/2509.24443)) treats scenario layers as the step after predictive maintenance. Here it's mostly composition, not new modeling; it belongs after the operating planner because it explains tradeoffs rather than assigning work.

### 3.4 Manager KPI Panel — deferred explain/manage follow-up (S, plus M for PM-compliance)

- **Seeds:** every input already sits in the in-memory SQLite read model — `delays` (minutes, tonnage), `incidents`, `logbook` closures, `feedback`, `notifications.jsonl`. `sql_query_tool` echoes SQL, so each KPI card is self-evidencing.
- **Computable today:** MTBF/MTTR per asset (incidents + delay durations), downtime tonnage, repeat-failure count, backlog age (logbook open vs closed), alert volume/dedup rate, stockout-at-risk parts (inventory × RUL).
- **Needs new data (generator change):** PM plans → PM compliance; labor hours → wrench time. List these as explicit gaps rather than faking them.
- **Why:** cheap credibility win for the supervisor/manager persona; the deferred plan keeps it as a SQL-evidenced helper (`kpi_summary`) rather than a new LLM tool, so it can render into Tab 1 or the Pre-Shift report without expanding the tool surface prematurely.

### 3.5 Spares Procurement Cockpit (M)

- **Seeds:** the constraint flip (lead time > RUL → monitored degradation) is the repo's signature behavior; `inventory_tool` already returns stock/lead/cost; `parts` is a SQL table; delay tonnage gives a stockout-cost proxy.
- **Build:** `procurement_tool(asset_id?)` — reorder recommendations (stock vs lead vs fleet RUL demand), expedite flag whenever `constraint_flag` fires, stockout cost estimate from historical delay tonnage, and a **draft purchase request as a markdown artifact** gated exactly like alerts (chat recommends; opted-in runs write). Substitute parts require a `substitute_of` column in the parts CSV (generator change).
- **Why:** after cascade/planner, this is the next best action-layer extension: it turns the existing constraint flip into a procurement queue instead of only a recommendation.

### 3.6 Governed Manager Copilot — plant-scope questions (M)

- **Seeds:** `sql_query_tool` (SELECT-only, SQL echoed), the trace expander, the five-block contract, and F1 in `docs/UX_JOURNEYS.md` ("One inbox for the plant"). The gap is purely *scope*: both modes currently funnel every query into a single-asset pipeline.
- **Build:** a plant-scope intent path after the cascade/planner backend and UI handoff land — expose a `plant_scan`/`shift_plan_tool` path if repeated manager questions need LLM access to the ranked table, plus SQL templates for questions like "which jobs can defer?", "this week's downtime risk?", and "which parts create schedule risk?". Deterministic mode needs a plant-level render variant (a sixth answer shape or a ranked-table block) — this is the real work and the eval cases must cover it.
- **Why governed:** this is the market's "evidence-grounded AI" direction; the repo's guardrails (SQL echo, trace, no invented values) already are the governance story — the feature is widening the question space, not loosening the rules.

### 3.7 Planner / Scheduler Board (L)

- **Seeds:** `shift_plan_tool` scheduled/deferred/procurement buckets; risk bands; lead times; delay tonnage as cost. §3.3's `scenario_tool(delay_days)` can later supply the "what if we delay 12/24/48 h" cell.
- **Missing data:** shift windows, permit status, backlog work orders, and real job dependencies. Crew/skill and job-duration templates now exist for the MVP, but the full board needs scheduling windows and operational constraints rather than only per-crew hour buckets.
- **Verdict:** highest manager value after the MVP, but the largest net-new surface (shift windows, permits, work orders, signoff, a sixth tab). Schedule after §3.1–3.6 so the board can consume `system_priority`, next-shift allocations, scenario deltas, and procurement state instead of being rebuilt around them later.

### 3.8 Reliability Engineering Workspace — FMEA/RCA (M)

- **Seeds:** `incidents` records; `feedback_tool` with outcome selector (confirmed/corrected/false alarm) and RAG re-indexing; the landed `fault_mode_tool` supplies a failure-mode taxonomy.
- **Build:** failure-mode column on incidents (generator), recurrence counts via SQL, an RCA template that appends to the logbook and re-indexes into RAG (so the next diagnosis cites the plant's own RCA — the existing learning loop, deepened), PM-strategy-change suggestions when recurrence > N.

### 3.9 HSE / Permit-to-Work Layer (S–M for config-driven; L for full PTW)

- **Seeds:** `task_closure_tool` + `CLOSURE_ITEMS` (already includes LOTO removal); SOP isolation steps in manuals; the two-step-confirm side-effect UX.
- **Build (config-driven first):** move checklist definitions to `config.py` keyed by permit type (LOTO / hot work / confined space), add a *pre-work* gate symmetrical to the closure gate, link incidents to permits. Full workflow (approvals, audit export) is v3.

### 3.10 Mobile Technician Mode — split it (S now, L later)

- **Seeds:** `docs/UIUX_SPEC.md` already designs the glove-first system (48 px targets, checklist-as-UI, mic input, wallboard mode) and lists the PWA shell as v2 candidate #1. F2 in `docs/UX_JOURNEYS.md` narrows the useful subset: QR deep link, glove-first SOP, voice/photo evidence, checklist carry-forward, named signoff.
- **S, inside Streamlit now:** QR deep links via query param (`?asset=VALVE-09` → Deep-Dive with focus set; QR codes printable from the asset registry), checklist state persisted into closure, `st.camera_input` photo evidence attached to logbook entries.
- **L, honest assessment:** true offline PWA with cached SOPs/checklists is a separate front-end; Streamlit cannot deliver it. Don't let "mobile" block the S items waiting for the L decision.

### 3.11 SAP IW38 CSV Adapter — work-order intake (M)

- **Seeds:** F1 step 2 in `docs/UX_JOURNEYS.md`; the repo already treats CSVs as governed system-of-record contracts, and `sql_query_tool` can expose any new table read-only once generated/loaded.
- **Build:** add a `work_orders` CSV contract for SAP IW38 exports (order id, asset id, order type, priority, status, due date, basic start/finish, planner group), a loader/normalizer that maps plant aliases to `asset_id`, and SQL-backed views for open maintenance/calibration work.
- **Why here:** it widens the "systems of record" intake without changing the reasoning loop, and it gives the manager copilot and daily board real backlog context instead of only inferred work.

### 3.12 Conversational Intake Intent Router — gated writes beyond feedback (M)

- **Seeds:** F1 step 3 and F2 step 3: "log a 40-min breakdown..." and voice/photo field capture. The repo already has the right safety pattern: chat recommends; write paths are opt-in and structured.
- **Build:** classify intake as breakdown / meter-reading / order-reference / closure-note / photo-evidence, render a review form with the parsed fields and cited source text, then write only after confirmation to `delays`, `incidents`, `logbook`, or attachment metadata. Deterministic fallback can use keyword rules; LLM mode can improve parsing behind the same review gate.
- **Why:** this is the bridge from decision support to operational capture, but it should wait until plant-scope evidence and work-order intake exist so it knows what tables and identities it is writing against.

### 3.13 User Identity & Signoff — named accountability (M)

- **Seeds:** F1 step 4 and F2 step 5; current closure is checklist-gated but effectively anonymous ("engineer").
- **Build:** a small users/roles data contract, signed logbook entries, named daily signoff, and audit fields on gated side effects (`created_by`, `approved_by`, `approved_at`). Keep auth lightweight for demo unless a deployment target requires real SSO.
- **Why:** identity is not flashy, but it unlocks signoff, daily management, permit workflow, and credible audit trails.

### 3.14 Legacy Document Ingestion — Word/Excel breakdown history (S–M)

- **Seeds:** F1 step 5; the RAG corpus already accepts markdown/manual chunks and feedback records, while incidents already serve root-cause context.
- **Build:** one-time import scripts for legacy `.docx` and `.xlsx` breakdown logs into normalized incident/delay rows plus asset-tagged RAG chunks. Require a review report for unmatched assets and ambiguous dates instead of silently ingesting bad history.
- **Why:** good demo value if the source files exist, but lower priority than live work-order/intake flows because it is migration support rather than a daily workflow.

### 3.15 Daily Management Board — tasks, signoff, exceptions (M–L)

- **Seeds:** F1 step 4; T2 pre-shift reports and T4 bottleneck board already provide the risk queue.
- **Build:** a board that joins risk queue + work orders + procurement blockers + signoff state. Start as a manager view over existing deterministic scans; expand only after `work_orders` and identity/signoff exist.
- **Why:** this is the natural front door for Shalini, but it should consume cascade, KPI, work-order, and signoff state rather than invent a parallel task model.

### 3.16 Vision-Based Inspection Intake — keep last (M, LLM-only)

- **No seeds**, and a structural caveat: Claude vision has **no deterministic rung**, so this can never join the offline pipeline or the eval baseline. Viable only as an on-demand evidence tool following the `fault_mode_tool` degradation pattern (`available: False` without a key), with findings written to the logbook and re-indexed into RAG. Real, but it serves the demo least per unit effort — schedule after everything above.

---

## 4. Recommended sequence

```
0. MW2 port                                      — landed baseline, do not queue
1. Cascade graph + system_priority               — asset → plant reasoning        [M]
2. Next-shift planner MVP                        — ranked work → allocated plan   [M]
3. Cascade/planner UI handoff                    — manager-visible operating view [S–M]
4. Procurement cockpit                           — constraint logic → action      [M]
5. Copilot plant-scope (plant_scan + SQL set)    — governed manager questions     [M]
6. scenario_tool + Workbook upgrade              — what-if on existing math       [S–M]
7. KPI panel (SQL-only metrics first)            — manager credibility            [S]
8. SAP IW38 CSV adapter                          — real work-order/backlog intake [M]
9. User identity + signoff                       — named gated actions            [M]
10. Conversational intake router                 — breakdown/voice/photo capture  [M]
11. Mobile-lite (QR, camera, checklist carry)    — technician journey subset      [S–M]
12. Daily management board                       — tasks, signoff, exceptions     [M–L]
13. Planner/scheduler board                      — needs windows/permits/orders   [L]
14. Reliability workspace (FMEA/RCA)             — uses landed fault taxonomy     [M]
15. HSE config-driven permit checklists          — extend the closure gate        [S–M]
16. Legacy document ingestion                    — migrate Word/Excel history     [S–M]
17. Vision intake (LLM-only evidence tool)       — after all of the above         [M]
```

Items 1–5 compound into the operating thesis: `system_priority` feeds `shift_plan_tool`, the UI handoff makes it visible, procurement closes the spares action loop, and plant-scope copilot questions widen it beyond one asset. Items 6–7 are the deferred explain/manage layer. Items 8–12 come directly from the F1/F2 user journeys: work-order intake, named accountability, gated operational capture, mobile evidence, and daily management.

## 5. Standing constraints on every feature (from `CLAUDE.md` / architecture doc)

1. New LLM-callable tools go in **both** `TOOL_FUNCS` and `TOOL_SCHEMAS`, with an eval case; add deterministic-pipeline dispatch only when the five-block diagnosis needs the tool every run (`fault_mode_tool` and planned `scenario_tool` are on-demand evidence tools).
2. The five-block contract is unchangeable; new evidence folds into existing blocks (cascade spec shows the pattern).
3. No hard top-level imports of production libraries; every new capability needs its degradation story stated (even if it's `available: False`).
4. Thresholds, weights, topology, and checklist definitions live in `config.py`, never inline.
5. Chat stays side-effect-free; anything that *acts* (PR drafts, alerts, permits) is opt-in gated like `alert_dispatch_tool`.
6. `python -m evals.judges` (plus the conformance suites) after every change.
