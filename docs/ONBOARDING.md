# Maintenance Wizard — Developer Onboarding Guide

> **Audience:** New developers joining the project.
> **Goal:** Get from zero to a working mental model and a running system in under an hour.

---

## What is this?

Maintenance Wizard is an autonomous decision-support agent for a heavy steel manufacturing plant. It fuses five data sources — live sensors, manuals/SOPs, delay logs, incident records, and ERP spare parts — into a single traceable maintenance decision.

It was built as a hackathon submission (Agentic AI Challenge Round 2). The README has the full conceptual framing if you want the pitch; this guide focuses on how the code actually works.

---

## Environment setup

### 1. Clone and install

```powershell
git clone <repo-url>
cd MaintenanceWiz_1
pip install -r requirements.txt
```

The core dependencies are just **numpy**, **pandas**, and **streamlit**. Everything else is optional:

| Package | What it upgrades | Without it |
|---|---|---|
| scikit-learn | Production RandomForest for RUL prediction | Pure-numpy bagged CART (`NumpyForest`) |
| shap | TreeSHAP feature attribution | Ablation attribution (reset-to-baseline) |
| chromadb | Vector-store RAG retrieval | TF-IDF cosine similarity (numpy) |
| anthropic | Claude tool-use loop (LLM mode) | Deterministic Python pipeline |
| matplotlib | Chart extras in the dashboard | Streamlit's built-in charts |

### 2. Run the data pipeline

Each step writes artifacts the next one consumes. **Order matters.**

```powershell
python data/generate_mock_data.py   # → data/*.csv, data/manuals/*.md, data/aliases.json
python ml/train_model.py            # → ml/artifacts/rul_model.pkl, feature_columns.json
python knowledge/rag.py             # → knowledge/store/ (Chroma or tfidf_index.pkl)
```

### 3. (Optional) Enable LLM mode

Copy `.env.example` to `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without this key, everything runs in deterministic mode — fully functional, just no Claude reasoning.

### 4. Launch

```powershell
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. You should see the Plant Bottleneck tab with 12 assets scored and ranked.

---

## The single most important concept

There are **two execution modes that share one tool suite**. Both must work at all times.

### LLM mode (`run_llm` in `agent/orchestrator.py`)

A single Claude tool-use loop. Claude reads the system prompt, receives the user's query, and decides which tools to call in what order. It writes the five-block answer itself.

This is the "Consolidated Brain" — one loop, no sub-agents, no delegation.

### Deterministic mode (`run_deterministic`)

The same tools called in a fixed pipeline order by Python code, with the five-block answer assembled by `_render()`. This is:

- The **offline fallback** (runs without an API key)
- The **reproducible baseline** the eval judges test against

### Why this matters to you

Both modes call the same functions in `agent/tools.py` via the same `TOOL_FUNCS` dispatch table. Both return `AgentResult` with the same `.trace` (observability) and `.structured` (machine-readable) contracts. The UI and evals are mode-agnostic.

**When you add or change a tool, you must update two things in `agent/orchestrator.py`:**

1. `TOOL_FUNCS` — the lambda dispatch table (used by both modes)
2. `TOOL_SCHEMAS` — the Anthropic JSON schemas (used by LLM mode only)

A tool added to only one will silently work in one mode and break in the other.

---

## Architecture walkthrough

### Data flow

```
User query
    │
    ▼
resolve_asset()          ← fuzzy match jargon to a formal asset_id
    │
    ├─► prognostic_tool()    ← RUL + failure prob + SHAP attribution
    ├─► abnormality_tool()   ← independent sensor deviation detection
    ├─► rag_tool()           ← SOP/manual/incident retrieval (asset-filtered)
    ├─► inventory_tool()     ← ERP spare parts + lead times
    ├─► delay_history_tool() ← production downtime history
    ├─► risk_score_tool()    ← weighted priority score + constraint flag
    └─► sql_query_tool()     ← ad-hoc SELECT over in-memory SQLite
    │
    ▼
Five-block answer (risk → diagnosis → blueprint → supply chain → audit trail)
```

In deterministic mode, this is a literal top-to-bottom pipeline. In LLM mode, Claude decides the order (guided by the system prompt).

### The fallback ladder

Every heavy dependency has a zero-dependency fallback:

| Layer | Production | Fallback | Key file |
|---|---|---|---|
| Prognostics | sklearn `RandomForestRegressor` | `NumpyForest` (bagged CART) | `ml/model.py` |
| Explainability | `shap.TreeExplainer` | Ablation attribution | `ml/model.py` |
| Retrieval | ChromaDB | `TfidfIndex` (numpy TF-IDF cosine) | `knowledge/rag.py` |
| Reasoning | Claude tool-use loop | Deterministic Python pipeline | `agent/orchestrator.py` |

Both estimators are wrapped in `RULModel` (pickled whole), so inference code never branches on which is inside. Both RAG backends expose the same `query(text, asset_id=None, k=4)` interface behind the `RAG` facade.

**Rule:** Never make a production library a hard import at module top level. Always try/except and fall back.

### Key files

| File | Role |
|---|---|
| `config.py` | Single source of truth — paths, NOMINAL baselines, thresholds, weights |
| `agent/orchestrator.py` | The brain — both execution modes, tool registries, `AgentResult` |
| `agent/tools.py` | All tool implementations — pure functions, individually testable |
| `agent/system_prompt.py` | LLM system prompt — defines the five-block output contract |
| `app/streamlit_app.py` | Dashboard — five tabs, mode-agnostic |
| `ml/model.py` | `RULModel` wrapper — sklearn or numpy, pickled whole |
| `ml/train_model.py` | Training — generates `rul_model.pkl` |
| `knowledge/rag.py` | RAG layer — build/load/query, Chroma or TF-IDF |
| `scripts/pre_shift_run.py` | Autonomous pre-shift briefing — cron-friendly |
| `evals/judges.py` | Regression guards — structured result + trace assertions |

---

## Key invariants (things that will break if you violate them)

### 1. `config.py` is the single source of truth

Paths, the `NOMINAL` healthy baselines, `RISK_WEIGHTS`, `PRIORITY_BANDS`, and `ALERT_THRESHOLD` all live here. The data generator, ML layer, and agent all import from it. If you need to change a threshold or weight, change it **here**, not inline somewhere else.

### 2. `SENSOR_FEATURES` order is a train/inference contract

The model is trained on per-asset-type *deviations* (z-scores vs `NOMINAL`), not raw readings. The feature order `["temperature", "vibration", "pressure", "humidity", "power"]` is baked into the model pickle. Don't reorder without retraining.

### 3. Manuals are keyed by `asset_id` filename

`data/manuals/GEARBOX-05.md` produces chunks tagged `asset_id="GEARBOX-05"`. RAG retrieval is asset-filtered, so the filename **is** the join key. Don't rename manual files without updating the data generator.

### 4. The five-block output is mandatory

Both modes must produce a response with `### 1.` through `### 5.` headers. The evals check all five are present. The deterministic renderer hardcodes them in `_render()`; the LLM is instructed via the system prompt.

### 5. Constraint-aware logic is a core demo behavior

In `risk_score_tool`: when an out-of-stock part's lead time exceeds predicted RUL, a `constraint_flag` fires and the recommendation flips from "replace now" to "monitored degradation." This is central to the demo — don't remove it.

### 6. `sql_query_tool` is SELECT-only

The tool builds an in-memory SQLite database from the CSVs (tables: `assets`, `sensors`, `delays`, `incidents`, `parts`). It only allows SELECT/WITH statements. It returns the exact SQL it ran for transparency.

### 7. No hallucination

The system prompt forbids inventing torque values, isolation steps, part numbers, or thresholds. Tool outputs are the only source of truth. Keep this constraint intact when editing prompts or the renderer.

---

## Common tasks with walkthroughs

### Adding a new tool

1. Write the function in `agent/tools.py`. Keep it pure — take structured input, return a dict.

2. Add a lambda entry to `TOOL_FUNCS` in `agent/orchestrator.py`:
   ```python
   "my_tool": lambda a: T.my_tool(a["param"]),
   ```

3. Add a schema entry to `TOOL_SCHEMAS` in the same file:
   ```python
   {"name": "my_tool", "description": "...",
    "input_schema": {"type": "object", "properties": {"param": {"type": "string"}}, "required": ["param"]}},
   ```

4. If the tool should run in the deterministic pipeline, add its `_dispatch()` call to `run_deterministic()` and incorporate its output into `_render()`.

5. Run `python -m evals.judges` to verify nothing broke.

### Adding a new asset type

1. Add its NOMINAL baselines to `config.py`:
   ```python
   "new_type": {"temperature": (mean, std), "vibration": ...},
   ```

2. Update `data/generate_mock_data.py` to generate data for the new type.

3. Re-run the full pipeline:
   ```powershell
   python data/generate_mock_data.py
   python ml/train_model.py
   python knowledge/rag.py
   ```

4. Create a manual file `data/manuals/NEW-ASSET-ID.md` with SOP sections.

### Modifying thresholds or weights

All thresholds live in `config.py`:

- `RISK_WEIGHTS` — how much RUL, criticality, delay history, and spares contribute to the priority score
- `PRIORITY_BANDS` — score cutoffs for CRITICAL/HIGH/MEDIUM/LOW
- `ALERT_THRESHOLD` — score at or above which auto-alerts fire
- `ANOMALY_WARNING_Z`, `ANOMALY_CRITICAL_Z` — z-score thresholds for the abnormality detector

After changing any of these, run `python -m evals.judges`. The eval cases expect specific priority bands, so you may need to update the expected values in `evals/judges.py` if the threshold change is intentional.

### Running the system end-to-end without LLM

Just don't set `ANTHROPIC_API_KEY`. Everything works — the deterministic pipeline calls the exact same tools in a fixed order and assembles the five-block answer programmatically. This is the default for development and testing.

### Testing a change

There is no test runner or linter. The regression guard is:

```powershell
python -m evals.judges
```

This runs four cases through the deterministic pipeline and asserts structured results land in expected bands. Run it after any change to tools, scoring, the system prompt, or the renderer.

Additional test suites in `evals/`:
- `requirement_judges.py` — PDF-mapped requirement conformance
- `tool_contract_tests.py` — tool input/output shape validation
- `reporting_tests.py` — report formatting tests

---

## How the five dashboard tabs map to the code

| Tab | What it does | Key functions called |
|---|---|---|
| Plant Bottleneck | Scores all assets, ranks by priority | `risk_score_tool()`, `abnormality_tool()` for each asset |
| Asset Deep-Dive | Shows one asset's sensors, SHAP, parts, workbook | `prognostic_tool()`, `abnormality_tool()`, `risk_score_tool()`, `inventory_tool()` |
| Wizard Chat | Free-text → five-block answer | `run_agent()` (picks LLM or deterministic mode) |
| Pre-Shift Report | Autonomous scan of urgent assets | `risk_score_tool()`, `prognostic_tool()`, `abnormality_tool()`, `inventory_tool()` |
| Digital Logbook | Job closure + feedback loop | `task_closure_tool()`, `record_feedback()`, `append_logbook()` |

---

## The feedback loop

Engineers can submit corrections and urgency adjustments via the Digital Logbook tab. This feeds two learning channels:

1. **RAG re-indexing:** The feedback text is added to the RAG corpus immediately, so the next diagnosis of that asset surfaces the engineer's own words.

2. **Priority calibration:** A `severity_adjust` (-25 to +25) is stored. By default, this does **not** affect the priority score (to keep the eval baseline reproducible). Enable with:
   ```powershell
   $env:MW_APPLY_FEEDBACK_BIAS = "1"
   ```

---

## Alert dispatch

Alerts are role-routed based on severity:

| Risk level | Routed to | Config key |
|---|---|---|
| CRITICAL | `shift-supervisor@plant.local` | `ALERT_ROLES["supervisor"]` |
| HIGH | `reliability-engineering@plant.local` | `ALERT_ROLES["reliability"]` |
| MEDIUM/LOW | `maintenance-team@plant.local` | `ALERT_ROLES["maintenance"]` |

Alerts are:
- **De-duplicated** per asset+band+day (won't spam the same alert)
- **Side-effect-free in chat** — the Wizard Chat tab only *recommends* alerts; the pre-shift script actually dispatches them
- **Logged** to `data/notifications.jsonl`

---

## Who to ask for what

| Topic | Where to look |
|---|---|
| How the scoring works | `config.py` (weights), `agent/tools.py:risk_score_tool` |
| Why a specific output was produced | The tool trace in the Wizard Chat expander, or `AgentResult.trace` |
| How the model was trained | `ml/train_model.py`, `ml/model.py` |
| What the LLM is told to do | `agent/system_prompt.py` |
| What the eval cases expect | `evals/judges.py` |
| Project goals and framing | `README.md` |
| Operational procedures | `docs/RUNBOOK.md` |
