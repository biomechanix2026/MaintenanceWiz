# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Maintenance Wizard is an autonomous industrial decision-support agent for a heavy steel plant. It fuses five data sources (live sensors, manuals/SOPs, delay logs, incident records, ERP spares) into one traceable maintenance decision, always emitted as the same **five-block output contract** (see `agent/system_prompt.py`). It is a hackathon submission (Agentic AI Challenge Round 2), so the README is unusually detailed — read it for the conceptual framing ("Consolidated Brain", "Systems of Action", smart-tools philosophy).

## Setup & commands

The data pipeline is ordered and must run before the app — each step writes artifacts the next consumes:

```bash
pip install -r requirements.txt        # optional; system runs on numpy+pandas+streamlit alone
python data/generate_mock_data.py      # writes data/*.csv, data/manuals/*.md, data/aliases.json
python ml/train_model.py               # writes ml/artifacts/rul_model.pkl (+ feature_columns.json)
python knowledge/rag.py                # builds the RAG index (Chroma store or knowledge/store/tfidf_index.pkl)
streamlit run app/streamlit_app.py     # the 5-panel dashboard
```

Other entry points:

```bash
python -m agent.orchestrator     # CLI demo of two queries through the full pipeline
python -m scripts.pre_shift_run  # autonomous briefing -> reports/preshift_*.md (cron-friendly)
python -m evals.judges           # eval suite; exits non-zero if any judge fails
```

There is **no test runner, linter, or build step** — `python -m evals.judges` is the closest thing to a test suite. Run it after any change to tools, scoring, the system prompt, or the deterministic renderer. Each case asserts the trace and structured result land in the expected band (not exact prose), so it's the regression guard.

LLM mode activates only when `ANTHROPIC_API_KEY` is set (copy `.env.example`); otherwise everything runs deterministically.

## Architecture: the two execution modes

The single most important thing to understand: there are **two execution modes that share one tool suite**, and both must keep working.

- **LLM mode** (`run_llm` in `agent/orchestrator.py`) — a single Claude tool-use loop with the full tool set. This is the "Consolidated Brain": one loop, no sub-agents.
- **Deterministic mode** (`run_deterministic`) — the same tools called in fixed pipeline order by Python, with the five-block answer assembled by `_render()`. This is the offline fallback **and** the reproducible baseline the evals judge against.

`run_agent()` picks the mode based on the API key. Both return the same `AgentResult` (with a `.trace` of `{tool, input, output}` dicts for observability), so the UI and evals are mode-agnostic.

**When adding or changing a tool, update both registries in `agent/orchestrator.py`:** `TOOL_FUNCS` (the lambda dispatch table both modes call) *and* `TOOL_SCHEMAS` (the Anthropic JSON schemas, LLM mode only). A tool added to only one will silently work in one mode and break in the other. The actual tool implementations live in `agent/tools.py` as pure, individually-testable functions.

## Architecture: the fallback ladder

Every heavy dependency has a zero-dependency fallback so the project runs on numpy+pandas+streamlit alone, and auto-upgrades when the real library is installed. Preserve this pattern when editing these layers — never make a production library a hard import at module top level:

| Layer | Production | Fallback | File |
|---|---|---|---|
| Prognostics | sklearn `RandomForestRegressor` | `NumpyForest` (bagged CART, numpy) | `ml/model.py`, `ml/train_model.py` |
| Explainability | `shap.TreeExplainer` | ablation attribution (reset each feature to baseline) | `ml/model.py` `RULModel.explain` |
| Retrieval | ChromaDB | `TfidfIndex` (numpy TF-IDF cosine) | `knowledge/rag.py` |
| Reasoning | Claude tool-use loop | deterministic Python pipeline | `agent/orchestrator.py` |

Both estimators are wrapped in one `RULModel` that is pickled whole, so inference never branches on which is inside. Both RAG backends expose the same `query(text, asset_id=None, k=4)` shape behind the `RAG` facade.

## Key invariants & contracts

- **`config.py` is the single source of truth.** Paths, the `NOMINAL` healthy baselines (the Semantic Layer's numeric backbone), `RISK_WEIGHTS`, `PRIORITY_BANDS`, and `ALERT_THRESHOLD` all live here. Data generator, ML, and agent layers all import from it so definitions never drift. Change a threshold or weight here, not inline.
- **`SENSOR_FEATURES` order is a train/inference contract.** The model is trained on per-asset-type *deviations* (z-scores vs `NOMINAL`), not raw readings — that's what lets one model serve furnaces, pumps, valves… and keeps SHAP physically meaningful. Don't reorder it without retraining.
- **Manuals are keyed by `asset_id` filename.** `data/manuals/GEARBOX-05.md` → chunks tagged `asset_id="GEARBOX-05"`. RAG retrieval is asset-filtered to prevent cross-asset bleed, so the filename *is* the join key.
- **The five-block output is mandatory** in both modes. Deterministic mode hardcodes `### 1.`…`### 5.` headers in `_render()`; the evals check all five are present. The LLM is instructed to produce them via `system_prompt.py`.
- **Constraint-aware logic** (`risk_score_tool` in `agent/tools.py`): when an out-of-stock part's lead time exceeds predicted RUL, the part physically cannot arrive before failure, so a `constraint_flag` fires and the recommendation flips from "replace now" to "monitored degradation". This is a central demo behavior — preserve it.
- **`sql_query_tool` is SELECT-only** over an in-memory SQLite DB built from the CSVs (tables: `assets`, `sensors`, `delays`, `incidents`, `parts`). It returns the exact SQL it ran for UI validation ("AI to build, UI to validate").
- **System-prompt guardrail:** tool outputs are the only source of truth — torque values, part numbers, isolation steps, and thresholds must never be invented from memory. Keep this constraint intact when editing prompts or the renderer.
