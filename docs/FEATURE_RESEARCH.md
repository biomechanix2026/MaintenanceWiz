# Maintenance Wizard — Feature Research (repo-grounded)

> **Date:** 2026-06-11
> **Scope:** Feature direction for *this* repo — every recommendation below is mapped to existing code, specs, or data contracts, not a generic CMMS checklist.
> **Companions:** `docs/ARCHITECTURE_DESIGN.md` (harness & invariants), `docs/UIUX_SPEC.md` (surfaces & personas), `docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md` (cascade spec), `docs/superpowers/plans/2026-06-11-mw2-port.md` (in-flight port plan).

---

## 1. Market direction (June 2026) → where this repo already stands

Strong maintenance platforms are converging on four themes. The repo's position against each:

| # | Market theme | Proxy | Repo position today |
|---|---|---|---|
| 1 | Mobile work execution (WOs, PMs, checklists, QR, meters, inventory) | [UpKeep features](https://upkeep.com/features/) | **Weakest axis.** UI/UX spec designs glove-first surfaces and an isolation checklist, but v1 is desktop Streamlit; no QR, offline, or photo capture. |
| 2 | AI-assisted EAM/APM (AI-prioritized work, CBM, visual inspection, inventory optimization, HSE) | [IBM Maximo](https://www.ibm.com/products/maximo) | **Strong on prioritization/CBM** (`risk_score_tool`, dual detectors, constraint flip); nothing on visual inspection; HSE is a single closure checklist. |
| 3 | Connected planning & scheduling (backlogs, skills, costs, parts replenishment) | [Oracle Maintenance](https://www.oracle.com/scm/maintenance/) | **Partial.** `pre_shift_run` produces a ranked action queue; no crew/skill/window data, no defer-impact analysis, no replenishment actions. |
| 4 | Evidence-grounded, governed AI (fused sources, deterministic verification) | [arXiv:2603.08171](https://arxiv.org/abs/2603.08171), [arXiv:2401.07871](https://arxiv.org/abs/2401.07871) | **The repo's identity.** Five-block contract, trace, SQL echo, deterministic baseline, eval judges. The in-flight MW2 port (hybrid BM25+RRF, sentence-level citations, fault classifier) extends exactly this theme. |

**Product angle confirmed by the codebase:** not "another CMMS," but a *maintenance command system* that converts sensor risk, SOP evidence, spares constraints, and production impact into an executable shift plan. Everything below serves that sentence.

---

## 2. In-flight work this research must sequence around

`docs/superpowers/plans/2026-06-11-mw2-port.md` is written, task-by-task, and unexecuted (all checkboxes open). It delivers: stdlib BM25 + RRF hybrid retrieval, native Anthropic citations + prompt caching in LLM mode, `fault_mode_tool` (12th tool, AI4I failure modes TWF/HDF/PWF/OSF/RNF), and a C-MAPSS RUL benchmark artifact. **This is market theme 4 and should land first** — it also creates two precedents later features reuse: the "on-demand evidence tool that degrades to `available: False`" pattern, and a failure-mode vocabulary the reliability workspace (§3.7) needs.

---

## 3. Feature priorities, grounded

Ordered by (demo value × seed maturity) ÷ effort. Effort: S < 1 day, M = days, L = week+ for this codebase's conventions (tool + dual registry + deterministic dispatch + eval case + UI).

### 3.1 Plant Cascade / Blast-Radius Prioritization — **build next** (M)

- **Seeds:** complete design spec (`docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`); README names it the one designed-but-unimplemented feature; the pitch deck already advertises `cascade_tool` as roadmap.
- **Build (per spec):** topology in `config.py` (`LINE_FLOW`, `UTILITY_EDGES`, `CASCADE_DECAY/GAIN`) → new pure `agent/cascade.py` → `cascade_tool` in both registries → Block 1 "System impact" line + Block 5 cascade path → `system_priority`/`downstream_count` columns and a graphviz topology view in the UI → cascade eval cases.
- **Why first:** it upgrades the system's unit of reasoning from *asset* to *plant* — the supervisor persona's actual question — and the spec already resolved the dangerous design choice (additive `system_priority`; `RISK_WEIGHTS` and existing judges untouched, so the eval baseline survives).

### 3.2 Scenario Simulation / "lightweight digital twin" — promoted, it's cheaper than it looks (S–M)

- **Seeds:** the Deep-Dive "Workbook" expander (`app/streamlit_app.py` ~line 154) already perturbs the five sensor readings ±50% and recomputes RUL via `model.predict_rul`. All other component math (abnormality z-scores, risk weights, constraint comparison) exists as pure functions.
- **Build:** `scenario_tool(asset_id, sensor_overrides, delay_days)` composing existing tool internals → recomputed RUL, abnormality status, priority band, constraint flag, and (after §3.1) `system_priority`. Register in both registries; host it in the existing Workbook expander; quick-chips in chat ("what if we wait 48 h?").
- **Direction match:** digital-twin literature ([arXiv:2509.24443](https://arxiv.org/abs/2509.24443)) treats scenario layers as the step after predictive maintenance. Here it's mostly composition, not new modeling.

### 3.3 Manager KPI Panel — promoted on effort/value (S, plus M for PM-compliance)

- **Seeds:** every input already sits in the in-memory SQLite read model — `delays` (minutes, tonnage), `incidents`, `logbook` closures, `feedback`, `notifications.jsonl`. `sql_query_tool` echoes SQL, so each KPI card is self-evidencing.
- **Computable today:** MTBF/MTTR per asset (incidents + delay durations), downtime tonnage, repeat-failure count, backlog age (logbook open vs closed), alert volume/dedup rate, stockout-at-risk parts (inventory × RUL).
- **Needs new data (generator change):** PM plans → PM compliance; labor hours → wrench time. List these as explicit gaps rather than faking them.
- **Why:** cheapest credibility win for the supervisor/manager persona; renders into Tab 1 or the Pre-Shift report without touching the harness.

### 3.4 Spares Procurement Cockpit (M)

- **Seeds:** the constraint flip (lead time > RUL → monitored degradation) is the repo's signature behavior; `inventory_tool` already returns stock/lead/cost; `parts` is a SQL table; delay tonnage gives a stockout-cost proxy.
- **Build:** `procurement_tool(asset_id?)` — reorder recommendations (stock vs lead vs fleet RUL demand), expedite flag whenever `constraint_flag` fires, stockout cost estimate from historical delay tonnage, and a **draft purchase request as a markdown artifact** gated exactly like alerts (chat recommends; opted-in runs write). Substitute parts require a `substitute_of` column in the parts CSV (generator change).
- **Why:** extends the architecture's most differentiated logic from *diagnosis* into *action* — the "Systems of Action" claim made executable.

### 3.5 Governed Manager Copilot — plant-scope questions (M)

- **Seeds:** `sql_query_tool` (SELECT-only, SQL echoed), the trace expander, the five-block contract. The gap is purely *scope*: both modes currently funnel every query into a single-asset pipeline.
- **Build:** a plant-scope intent path — expose a `plant_scan` tool (today it's UI-side logic) in both registries, plus SQL templates for the manager's questions ("which jobs can defer?", "this week's downtime risk?", "which parts create schedule risk?"). Deterministic mode needs a plant-level render variant (a sixth answer shape or a ranked-table block) — this is the real work and the eval cases must cover it.
- **Why governed:** this is the market's "evidence-grounded AI" direction; the repo's guardrails (SQL echo, trace, no invented values) already are the governance story — the feature is widening the question space, not loosening the rules.

### 3.6 Planner / Scheduler Board (L)

- **Seeds:** `pre_shift_run` ranked queue; risk bands; lead times; delay tonnage as cost. §3.2's `scenario_tool(delay_days)` supplies the "what if we delay 12/24/48 h" cell.
- **Missing data:** crews, skills, shift windows, permit status — a new CSV family from `generate_mock_data.py` plus an assignment heuristic (greedy: severity-ordered jobs → skill-matched crew → window fit).
- **Verdict:** highest manager value after cascade, but the largest net-new surface (new data contracts + a sixth tab). Schedule after §3.1–3.5 so the board can consume `system_priority`, scenario deltas, and procurement state instead of being rebuilt around them later.

### 3.7 Reliability Engineering Workspace — FMEA/RCA (M)

- **Seeds:** `incidents` records; `feedback_tool` with outcome selector (confirmed/corrected/false alarm) and RAG re-indexing; the MW2 port's `fault_mode_tool` supplies a failure-mode taxonomy.
- **Build:** failure-mode column on incidents (generator), recurrence counts via SQL, an RCA template that appends to the logbook and re-indexes into RAG (so the next diagnosis cites the plant's own RCA — the existing learning loop, deepened), PM-strategy-change suggestions when recurrence > N.

### 3.8 HSE / Permit-to-Work Layer (S–M for config-driven; L for full PTW)

- **Seeds:** `task_closure_tool` + `CLOSURE_ITEMS` (already includes LOTO removal); SOP isolation steps in manuals; the two-step-confirm side-effect UX.
- **Build (config-driven first):** move checklist definitions to `config.py` keyed by permit type (LOTO / hot work / confined space), add a *pre-work* gate symmetrical to the closure gate, link incidents to permits. Full workflow (approvals, audit export) is v3.

### 3.9 Mobile Technician Mode — split it (S now, L later)

- **Seeds:** `docs/UIUX_SPEC.md` already designs the glove-first system (48 px targets, checklist-as-UI, mic input, wallboard mode) and lists the PWA shell as v2 candidate #1.
- **S, inside Streamlit now:** QR deep links via query param (`?asset=VALVE-09` → Deep-Dive with focus set; QR codes printable from the asset registry), checklist state persisted into closure, `st.camera_input` photo evidence attached to logbook entries.
- **L, honest assessment:** true offline PWA with cached SOPs/checklists is a separate front-end; Streamlit cannot deliver it. Don't let "mobile" block the S items waiting for the L decision.

### 3.10 Vision-Based Inspection Intake — keep last (M, LLM-only)

- **No seeds**, and a structural caveat: Claude vision has **no deterministic rung**, so this can never join the offline pipeline or the eval baseline. Viable only as an on-demand evidence tool following the `fault_mode_tool` degradation pattern (`available: False` without a key), with findings written to the logbook and re-indexed into RAG. Real, but it serves the demo least per unit effort — schedule after everything above.

---

## 4. Recommended sequence

```
0. Execute the MW2 port plan (already written)   — theme 4: citations, hybrid RAG, fault modes
1. Cascade graph (spec'd)                        — asset → plant reasoning        [M]
2. scenario_tool + Workbook upgrade              — what-if on existing math       [S–M]
3. KPI panel (SQL-only metrics first)            — manager credibility            [S]
4. Procurement cockpit                           — constraint logic → action      [M]
5. Copilot plant-scope (plant_scan + SQL set)    — governed manager questions     [M]
6. Planner/scheduler board                       — needs new mock-data contracts  [L]
7. HSE config-driven permit checklists           — extend the closure gate        [S–M]
8. Reliability workspace (FMEA/RCA)              — deepen the learning loop       [M]
9. Mobile-lite (QR deep links, camera, persist)  — Streamlit-feasible subset      [S]
10. Vision intake (LLM-only evidence tool)       — after all of the above         [M]
```

Items 1–5 compound: the planner board (6) then assembles `system_priority` + scenario deltas + procurement state + KPIs into the shift plan — the product angle in one screen.

## 5. Standing constraints on every feature (from `CLAUDE.md` / architecture doc)

1. New tools go in **both** `TOOL_FUNCS` and `TOOL_SCHEMAS`, with a deterministic-pipeline dispatch and an eval case — or they silently break one mode.
2. The five-block contract is unchangeable; new evidence folds into existing blocks (cascade spec shows the pattern).
3. No hard top-level imports of production libraries; every new capability needs its degradation story stated (even if it's `available: False`).
4. Thresholds, weights, topology, and checklist definitions live in `config.py`, never inline.
5. Chat stays side-effect-free; anything that *acts* (PR drafts, alerts, permits) is opt-in gated like `alert_dispatch_tool`.
6. `python -m evals.judges` (plus the conformance suites) after every change.
