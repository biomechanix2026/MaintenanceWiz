# Maintenance Wizard — Agentic Harness, Framework & System Architecture

> **Status:** Target design (v2), evolving the working v1 prototype.
> **Primary logic foundation:** `docs/ONBOARDING.md`. Requirements source: `document_pdf.pdf` (Agentic AI Challenge Round 2).
> **Companion document:** `docs/UIUX_SPEC.md` — UI/UX specification for steel-plant maintenance teams.

---

## 1. Design goal

Design a Claude-like agentic harness — a single reasoning loop with a curated tool suite, strict grounding guardrails, full observability, and a deterministic fallback — that solves the problem statement's six objectives (diagnosis, root cause, RUL prediction, abnormality early-warning, constraint-aware prioritization, structured reporting) for a heavy steel plant, while remaining demoable offline and reproducible under evals.

The v1 codebase already embodies the right skeleton. This document formalizes it as an architecture, names its contracts, and specifies the v2 evolution path. **Every invariant in `ONBOARDING.md` is preserved.**

---

## 2. Requirements → architecture traceability

| PDF requirement | Architectural answer | Component |
|---|---|---|
| 4.1 Delay logs, faults, incidents | CSV/ERP ingestion → SQLite read model + RAG corpus | Data plane, `sql_query_tool`, `delay_history_tool` |
| 4.2 Sensor summaries, anomaly alerts | Sensor store → deviation features vs `NOMINAL` | `abnormality_tool`, `prognostic_tool` |
| 4.3 Manuals, SOPs, spares + lead time | Asset-keyed RAG index; ERP parts table | `rag_tool`, `inventory_tool` |
| 4.4 NL queries, multi-turn | Harness conversation state (`history`, `focus_asset`) | Orchestrator |
| 5.1 Diagnosis, root cause, RUL, early warning | RUL regressor + SHAP + independent z-score detector + incident retrieval | ML plane + tools |
| 5.2 Risk bands, urgency, plant bottleneck, constraint-based priority | Deterministic `risk_score_tool` with `RISK_WEIGHTS`, `PRIORITY_BANDS`, `constraint_flag` | `config.py` + tools |
| 5.3 Step-by-step actions, plans, procurement strategy | Five-block output contract, blocks 3–4 | System prompt / `_render()` |
| 5.4 Reports, alert reports, decision summaries, digital log | Pre-shift script, alert dispatcher, logbook tools | Action plane |
| 6.1 LLM/SLM reasoning | Claude tool-use loop (LLM mode) | Harness |
| 6.2 Knowledge integration | Five fused sources behind one tool suite | Tool suite |
| 6.3 NL multi-turn interaction | History windowing + focus-asset anaphora | Harness |
| 6.4 Explainability/traceability | `AgentResult.trace`, block 5 audit trail, SQL echo | Observability |
| 6.5 Abnormality detection & failure prediction | Dual independent detectors (regressor + z-score) | ML plane |
| 6.6 Feedback-driven improvement | Two-channel feedback loop (RAG re-index + opt-in priority bias) | Learning plane |
| 6.7 Real-time alerting | Role-routed, deduped, side-effect-gated dispatcher | Action plane |
| 7 Optional: dashboard, IoT sim, dynamic KB, logbook, role alerts | All implemented (5-tab UI, mock sensor generator, per-asset manuals, logbook, `ALERT_ROLES`) | UI + action planes |

---

## 3. The agentic harness (Claude-like core)

The harness is the contract between the reasoning engine and the world. It is deliberately modeled on the Claude agent pattern: **one loop, one tool registry, grounded outputs, full trace.**

### 3.1 The loop

```
                    ┌────────────────────────────────────────────┐
 user query ───►    │  HARNESS                                   │
 history ──────►    │  ┌──────────┐   tool_use   ┌────────────┐  │
 focus_asset ──►    │  │ Reasoner  │────────────►│ Dispatcher │  │
                    │  │ (Claude / │◄────────────│ TOOL_FUNCS │  │
                    │  │  determ.) │  tool_result└─────┬──────┘  │
                    │  └────┬─────┘                    │ append  │
                    │       │ final text          ┌────▼─────┐   │
                    │       ▼                     │  trace[]  │   │
                    │  five-block answer          └──────────┘   │
                    └────────────────────────────────────────────┘
                         │
                         ▼
              AgentResult { answer_markdown, asset_id, mode, trace, structured }
```

Think → act → observe, bounded by `max_steps` (8). No sub-agents, no delegation — the **Consolidated Brain** principle: the full system context and the entire tool suite live inside one loop, which keeps reasoning traceable and eliminates inter-agent state drift.

### 3.2 Dual reasoner, single harness

The defining property (per `ONBOARDING.md`): **two execution modes share one tool suite, and both must always work.**

| | LLM mode (`run_llm`) | Deterministic mode (`run_deterministic`) |
|---|---|---|
| Planner | Claude decides tool order | Fixed pipeline (Step 0→5) |
| Renderer | Claude writes five blocks per system prompt | `_render()` hardcodes `### 1.`–`### 5.` |
| Role | Production reasoning | Offline fallback **and** eval baseline |
| Activation | `ANTHROPIC_API_KEY` set | Default; also auto-fallback on LLM exception |

`run_agent()` selects the mode; both return the same `AgentResult`, so UI, evals, logbook, and reports are mode-agnostic. The deterministic pipeline is not a degraded clone — it is the **reproducible specification** of correct behavior that the LLM is prompted to match, and the regression target for `evals/judges.py`.

### 3.3 Tool registry — the dual-registration contract

Every tool exists in two registries in `agent/orchestrator.py`:

1. `TOOL_FUNCS` — lambda dispatch table (both modes call through it)
2. `TOOL_SCHEMAS` — Anthropic JSON schemas (LLM mode only)

A tool added to only one silently works in one mode and breaks in the other. **v2 hardening:** add a startup assertion `set(TOOL_FUNCS) == {s["name"] for s in TOOL_SCHEMAS}` plus a contract test in `evals/tool_contract_tests.py` so the invariant is machine-enforced, not tribal knowledge.

Implementations stay in `agent/tools.py` as pure functions: structured input → dict out, individually testable, no hidden state.

### 3.4 The tool suite (smart tools, thin agent)

| Tool | Capability | PDF mapping |
|---|---|---|
| `resolve_asset` | Fuzzy jargon → formal `asset_id` (aliases.json); confidence-gated clarification | 4.4 NL input |
| `prognostic_tool` | RUL days, 30-day failure probability, SHAP attribution | 5.1 RUL |
| `abnormality_tool` | Independent z-score deviation + trend detector, catastrophic flag | 5.1 / 6.5 early warning |
| `rag_tool` | Asset-filtered SOP/manual/incident retrieval | 4.3 / 6.2 knowledge |
| `inventory_tool` | Spares stock, lead times, cost | 5.2 spares basis |
| `delay_history_tool` | Downtime events, minutes, tonnage lost | 5.2 delay severity |
| `risk_score_tool` | Weighted 0–100 priority, band, **constraint_flag** | 5.2 prioritization |
| `sql_query_tool` | SELECT-only ad-hoc analytics; echoes the SQL run | 6.4 traceability |
| `alert_dispatch_tool` | Role-routed, deduped, dry-run-gated alerts | 6.7 real-time alerting |
| `task_closure_tool` | Compliance checklist gate for work-order closure | 5.4 logbook |
| `feedback_tool` | Engineer correction → RAG re-index + severity_adjust | 6.6 feedback loop |

Intelligence is pushed **into the tools** (deviation math, weighted scoring, constraint detection) so the reasoning layer composes verified facts rather than computing them — this is what makes the deterministic fallback possible at all.

### 3.5 Grounding guardrails (zero-hallucination)

From the system prompt, preserved verbatim in spirit:

- Tool outputs are the **only** source of truth. Torque values, isolation steps, part numbers, thresholds are never produced from model memory.
- Every technical recommendation cites its source (manual section or incident ID) in block 5.
- `sql_query_tool` is SELECT-only and returns the exact SQL for UI validation ("AI to build, UI to validate").
- If data is missing, the answer says so rather than filling the gap.
- `resolve_asset` confidence < 0.7 → ask one clarifying question instead of guessing the asset.

### 3.6 Side-effect policy

A diagnostic chat query must be **side-effect-free**. Alert dispatch is dry-run unless the caller (pre-shift monitor, scheduled scan) opts in with `dispatch_alerts=True`. Chat *recommends*; autonomous runs *act*. Alerts are deduped per asset+band+day and logged to `data/notifications.jsonl`. This split is the harness's action-safety boundary and must survive any refactor.

### 3.7 Multi-turn context

- `history` — last 6 user/assistant text turns prepended (tool plumbing re-derived each turn, never replayed).
- `focus_asset` — the asset in conversational focus; resolves anaphora ("what about its bearings?") identically in both modes (deterministic: resolution fallback; LLM: injected context line).

**v2:** persist focus + open work-order context per session in the UI session state so a technician can resume a conversation after a floor interruption.

### 3.8 Observability

`AgentResult.trace` is a list of `{tool, input, output}` — the complete, ordered record of everything the agent did. It feeds:

- the UI trace expander (every answer is auditable on-screen),
- `evals/judges.py` (assertions on trace shape, not prose),
- block 5 of every answer (human-readable audit trail),
- the digital logbook (`structured` snapshot stored with each closure).

**v2:** add per-tool latency and a monotonically increasing `step` index to each trace entry; emit traces as JSONL for offline analysis.

### 3.9 Output contract

Every answer, both modes, is the **five-block contract**:

1. Operational Risk Assessment — band, score, RUL, failure probability, abnormality status, delay severity
2. Diagnostic & Root-Cause Breakdown — probable fault, SHAP drivers, abnormal evidence, attribution method
3. Actionable Maintenance Blueprint — isolation steps from the cited SOP, verified repair tasks, long-term plan
4. Supply-Chain Logistics Strategy — per-part stock/lead/cost, mitigation
5. Traceability & Audit Trail — SOP sources, incident IDs, the SQL run, feedback count

This is simultaneously the answer format, the eval assertion target, and the UI rendering schema. It maps 1:1 onto PDF §5.1–5.4.

---

## 4. Agentic framework (the layered system around the harness)

```
┌─────────────────────────── UI / EXPERIENCE PLANE ───────────────────────────┐
│ Streamlit 5-tab dashboard · Wizard Chat · trace viewer · logbook            │  → UIUX_SPEC.md
├─────────────────────────────── ACTION PLANE ────────────────────────────────┤
│ alert_dispatch (role-routed, deduped) · pre_shift_run (cron) · task_closure │
│ logbook append · notifications.jsonl                                        │
├────────────────────────────── REASONING PLANE ──────────────────────────────┤
│ THE HARNESS: run_agent → run_llm | run_deterministic                        │
│ TOOL_FUNCS + TOOL_SCHEMAS · system_prompt (five-block contract, guardrails) │
├────────────────────────────── CAPABILITY PLANE ─────────────────────────────┤
│ agent/tools.py — 11 pure smart tools                                        │
├──────────────────────────── INTELLIGENCE PLANE ─────────────────────────────┤
│ RULModel (sklearn RF ⇄ NumpyForest) · SHAP ⇄ ablation · z-score detector    │
│ RAG facade (Chroma ⇄ TF-IDF) — asset-keyed corpus                           │
├────────────────────────────── SEMANTIC PLANE ───────────────────────────────┤
│ config.py — single source of truth: NOMINAL baselines, SENSOR_FEATURES      │
│ order, RISK_WEIGHTS, PRIORITY_BANDS, ALERT_THRESHOLD, ALERT_ROLES           │
├──────────────────────────────── DATA PLANE ─────────────────────────────────┤
│ sensors · delays · incidents · ERP parts · manuals/SOPs (asset-keyed .md)   │
│ in-memory SQLite read model · aliases.json · feedback.csv · logbook.csv     │
└─────────────────────────────────────────────────────────────────────────────┘
                 LEARNING LOOP (cross-cutting): feedback_tool →
        ① immediate RAG re-index   ② opt-in priority bias (MW_APPLY_FEEDBACK_BIAS)
```

### 4.1 The fallback ladder (resilience as architecture)

Every heavy dependency has a zero-dependency fallback; the system runs on numpy+pandas+streamlit alone and auto-upgrades when libraries are present:

| Layer | Production | Fallback |
|---|---|---|
| Prognostics | sklearn RandomForest | `NumpyForest` (bagged CART) |
| Explainability | `shap.TreeExplainer` | Ablation attribution (reset-to-baseline) |
| Retrieval | ChromaDB | `TfidfIndex` (numpy TF-IDF cosine) |
| Reasoning | Claude tool-use loop | Deterministic Python pipeline |

Rules that make this work: never hard-import a production library at module top level (try/except, fall back); wrap both estimators in one pickled `RULModel` so inference never branches; both RAG backends expose `query(text, asset_id=None, k=4)` behind one facade. For a steel plant — where the network is unreliable and air-gapped deployments are common — **graceful degradation is a first-class requirement**, not an optimization.

### 4.2 Semantic plane

`config.py` is the numeric backbone. `NOMINAL` per-asset-type healthy baselines turn raw readings into physically meaningful z-deviations, which is what lets **one model serve furnaces, pumps, valves, mills, gearboxes, compressors, cranes, conveyors** and keeps SHAP interpretable ("vibration is +3.1σ above healthy" rather than "feature_2 = 5.7"). `SENSOR_FEATURES` order is a train/inference contract — never reorder without retraining.

### 4.3 Learning plane (feedback-driven improvement)

Two channels, deliberately asymmetric:

1. **RAG re-indexing (always on):** engineer feedback text enters the corpus immediately; the next diagnosis of that asset surfaces the engineer's own words. Fast, safe, additive.
2. **Priority calibration (opt-in):** `severity_adjust` ∈ [−25, +25] stored per asset; affects `risk_score_tool` only when `MW_APPLY_FEEDBACK_BIAS=1`, keeping the eval baseline reproducible and the headline score grounded purely in its stated basis.

**v2:** periodic retraining job that folds confirmed-outcome feedback into RUL training labels; feedback provenance shown in block 5 (`feedback_count`, applied Δ).

### 4.4 Autonomy plane

`scripts/pre_shift_run.py` is the autonomous mode: scan all assets, score, dispatch live role-routed alerts, write `reports/preshift_*.md`. Cron-friendly. This is the "Systems of Action" half — the same brain, run proactively instead of reactively, which directly answers the PDF's "shift from reactive to proactive" outcome.

**v2:** add a continuous monitor variant (5-min cadence) that calls only `abnormality_tool` + `risk_score_tool` per asset (cheap, no LLM) and triggers a full five-block diagnosis only on band escalation.

---

## 5. System architecture & data flow

### 5.1 End-to-end query flow

```
"the caster valve is leaking again"
   │
   ▼ STEP 0 resolve_asset ── aliases.json fuzzy match → VALVE-09 (conf 0.86)
   ▼ STEP 1 prognostic_tool ── RUL 11d, P(fail,30d) 74%, SHAP: pressure +3.4σ
   │         abnormality_tool ── CRITICAL 82/100, pressure breach, rising trend
   ▼ STEP 2 rag_tool(asset=VALVE-09) ── SOP-VALVE-09 §Isolation, INC-2031, INC-1988
   │         sql_query_tool ── delay codes grouped by downtime (SQL echoed)
   ▼ STEP 3 inventory_tool ── seal kit OUT OF STOCK, lead 21d > RUL 11d
   ▼ STEP 4 risk_score_tool ── 87/100 CRITICAL + constraint_flag fires
   ▼ STEP 5 reconcile → five-block answer
            └─ recommendation flips: "replace now" → "monitored degradation"
            └─ alert recommended (≥ ALERT_THRESHOLD); dispatched only if opted in
```

The **constraint-aware flip** is the architecture's signature behavior: when lead time > RUL, the part physically cannot arrive before failure, so the blueprint becomes tightened alarms + interim mitigation + expedited procurement. Preserve it in any refactor.

### 5.2 Data pipeline (ordered; each step feeds the next)

```
generate_mock_data.py → data/*.csv, manuals/*.md, aliases.json
        └→ train_model.py → ml/artifacts/rul_model.pkl (+feature_columns.json)
                └→ knowledge/rag.py → knowledge/store/ (Chroma or tfidf_index.pkl)
                        └→ streamlit_app.py / pre_shift_run.py / evals
```

Manuals are keyed by `asset_id` filename (`GEARBOX-05.md` → chunks tagged `GEARBOX-05`); retrieval is asset-filtered to prevent cross-asset bleed. The filename **is** the join key. In production, the mock generator is replaced by adapters (historian/OPC-UA for sensors, ERP export for parts, CMMS export for delays/incidents) writing the same CSV contracts — nothing downstream changes.

### 5.3 Technology stack

| Concern | Choice | Why |
|---|---|---|
| Core runtime | Python, numpy, pandas | Universal, offline-capable |
| Reasoning | Claude (Sonnet) tool-use API; deterministic Python fallback | Best-in-class tool use; zero-dependency fallback |
| ML | sklearn RF ⇄ NumpyForest; SHAP ⇄ ablation | Fallback ladder |
| Retrieval | ChromaDB ⇄ numpy TF-IDF | Fallback ladder |
| Read model | In-memory SQLite from CSVs | SELECT-only safety, zero infra |
| UI | Streamlit | Rapid, mode-agnostic dashboard |
| Scheduling | cron / Task Scheduler → pre_shift_run | No broker needed |
| Quality | evals/judges.py (+ requirement, contract, reporting suites) | Regression guard in lieu of a test runner |

### 5.4 Quality & evals (the regression guard)

`python -m evals.judges` is the test suite: four cases through the deterministic pipeline asserting structured results land in expected **bands** (not exact prose) and traces have the right shape. Run after any change to tools, scoring, the system prompt, or the renderer. Companion suites: `requirement_judges.py` (PDF-mapped conformance), `tool_contract_tests.py` (tool I/O shapes), `reporting_tests.py` (report formatting). Threshold changes in `config.py` may legitimately require updating expected bands — that is a reviewed, intentional act.

**v2:** add LLM-mode spot evals (same cases, judge that all five blocks are present and every cited source exists in the trace) and the registry-parity assertion from §3.3.

---

## 6. Assumptions & limitations

- Sensor data is batch CSV in v1; "real-time" means scheduled scans, not streaming. v2 monitor loop (§4.4) narrows this gap without new infrastructure.
- Mock data generator stands in for plant historians/ERP; adapters preserve the CSV contracts.
- Alert "dispatch" writes to `notifications.jsonl` with role addresses; SMTP/webhook delivery is a thin v2 adapter behind the same tool.
- The RUL model is trained on synthetic degradations; accuracy claims apply to the architecture, not field-calibrated predictions, until retrained on plant history.
- Single-plant, single-tenant scope; no authentication layer in v1 (UI spec defines role views for v2).

---

## 7. Invariants checklist (do not break)

1. `config.py` is the single source of truth for thresholds, weights, baselines, paths.
2. `SENSOR_FEATURES` order is a train/inference contract.
3. Manual filename = `asset_id` = RAG join key.
4. Five-block output is mandatory in both modes.
5. Constraint flip (lead time > RUL → monitored degradation) is core behavior.
6. `sql_query_tool` is SELECT-only and echoes its SQL.
7. Tool outputs are the only source of truth — no invented values.
8. Both registries (`TOOL_FUNCS`, `TOOL_SCHEMAS`) updated together for every tool change.
9. Chat is side-effect-free; only opted-in autonomous runs dispatch alerts.
10. Run `python -m evals.judges` after any change to tools, scoring, prompt, or renderer.
