# Maintenance Wizard — Operational Runbook

> **Audience:** Anyone who needs to start, stop, troubleshoot, or recover the system.
> **Last updated:** 2026-06-09

---

## When to use this runbook

- First-time setup on a new machine
- Starting the dashboard or scheduled jobs
- Diagnosing why a pipeline step or the UI is broken
- Recovering from data corruption or missing artifacts
- Understanding what each execution mode does and when to switch

---

## Prerequisites

| Requirement | Minimum | Check command |
|---|---|---|
| Python | 3.10+ | `python --version` |
| pip packages | numpy, pandas, streamlit | `pip install -r requirements.txt` |
| Disk space | ~200 MB (data + artifacts + vector store) | — |
| API key (optional) | `ANTHROPIC_API_KEY` in `.env` | `echo $env:ANTHROPIC_API_KEY` |

The system runs fully without scikit-learn, shap, chromadb, or anthropic. These are optional upgrades (see the fallback ladder in the onboarding guide).

---

## 1. Full setup from scratch

The data pipeline is **ordered** — each step writes artifacts the next consumes. Run them in sequence:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate mock plant data (writes data/*.csv, data/manuals/*.md, data/aliases.json)
python data/generate_mock_data.py

# 3. Train the RUL prognostic model (writes ml/artifacts/rul_model.pkl + feature_columns.json)
python ml/train_model.py

# 4. Build the RAG knowledge index (writes knowledge/store/tfidf_index.pkl or Chroma DB)
python knowledge/rag.py

# 5. Launch the dashboard
streamlit run app/streamlit_app.py
```

**If any step fails**, check the section below for that specific failure before continuing.

---

## 2. Starting the dashboard

```powershell
streamlit run app/streamlit_app.py
```

The dashboard opens at `http://localhost:8501`. It has five tabs:

| Tab | Purpose |
|---|---|
| Plant Bottleneck | All assets ranked by priority score — the triage view |
| Asset Deep-Dive | Sensors, SHAP attribution, spare parts, interactive workbook |
| Wizard Chat | Free-text queries → five-block diagnostic answer + tool trace |
| Pre-Shift Report | Autonomous briefing with drafted work orders |
| Digital Logbook | Job closure checklist + engineer feedback loop |

### Execution mode

The dashboard auto-selects the execution mode:

- **`ANTHROPIC_API_KEY` is set** → LLM mode (Claude tool-use loop). The header shows "LLM (Claude)".
- **No key** → Deterministic mode (fixed Python pipeline). The header shows "Deterministic (offline)".

To switch modes: set or unset the key, then restart Streamlit.

```powershell
# Enable LLM mode
$env:ANTHROPIC_API_KEY = "sk-ant-..."
streamlit run app/streamlit_app.py

# Or run purely deterministic (unset the key)
Remove-Item Env:ANTHROPIC_API_KEY
streamlit run app/streamlit_app.py
```

---

## 3. Running the pre-shift briefing

The pre-shift script scans every asset, drafts work orders for CRITICAL/HIGH/abnormal assets, dispatches alerts, and writes a timestamped markdown report.

```powershell
python -m scripts.pre_shift_run
```

**Output:** `reports/preshift_YYYYMMDD_HHMM.md`

### Scheduling (cron / Task Scheduler)

Run daily before the morning shift. Example cron entry:

```
0 6 * * *  cd /path/to/MaintenanceWiz_1 && python -m scripts.pre_shift_run
```

On Windows Task Scheduler, create a basic task that runs:
```
python -m scripts.pre_shift_run
```
with "Start in" set to the project root directory.

---

## 4. Running the eval suite

The eval judges are the project's regression guard. Run them after any change to tools, scoring, the system prompt, or the deterministic renderer.

```powershell
python -m evals.judges
```

**Expected output:** `RESULT: 4/4 judges passed` with exit code 0.

If any judge fails, the output shows which specific check failed (asset resolution, priority band, constraint flag, five-block output, etc.). Fix the regression before merging.

Additional eval suites:
```powershell
python -m evals.requirement_judges    # PDF-mapped requirement conformance
python -m evals.tool_contract_tests   # Tool input/output contract checks
python -m evals.reporting_tests       # Reporting format tests
```

---

## 5. CLI demo (ad-hoc queries)

```powershell
python -m agent.orchestrator
```

Runs two sample queries through the full pipeline and prints the five-block answer with mode/asset/tool-count metadata. Useful for quick smoke tests.

---

## 6. Troubleshooting

### "No sensor data for ASSET-ID"

**Cause:** The data generation step was skipped or the CSV is missing/empty.

**Fix:**
```powershell
python data/generate_mock_data.py
```
Then restart the dashboard.

### "FileNotFoundError: rul_model.pkl"

**Cause:** The model training step was skipped.

**Fix:**
```powershell
python ml/train_model.py
```

### RAG returns low-quality or no results

**Cause:** The RAG index is stale or was never built.

**Fix:**
```powershell
python knowledge/rag.py
```
This rebuilds the full index (Chroma if available, TF-IDF fallback otherwise). The tools lazy-load the index, so restart the dashboard after rebuilding.

### "LLM mode failed; used deterministic pipeline"

This message in the chat output means LLM mode was attempted but the API call failed. The system auto-fell back to deterministic mode. Common causes:

- Invalid or expired `ANTHROPIC_API_KEY`
- Network connectivity issues
- API rate limits

**Fix:** Check `.env`, verify the key, and test connectivity. The deterministic pipeline is fully functional — this is a graceful degradation, not a crash.

### Dashboard is slow on first load

The Plant Bottleneck tab scores every asset on first load (cached afterward). With 12 assets this takes a few seconds. If it's much slower:

- Check that `ml/artifacts/rul_model.pkl` exists (avoids re-training on load)
- Check that `knowledge/store/` has an index file (avoids re-indexing on load)

### Eval judge fails after a code change

The judges check structured results and tool traces, not exact prose. A failure means the logic changed, not just the wording. Check:

1. Did you change `config.py` thresholds (`RISK_WEIGHTS`, `PRIORITY_BANDS`, `ALERT_THRESHOLD`)? The eval cases expect specific priority bands.
2. Did you modify a tool's return shape? Both `TOOL_FUNCS` and `TOOL_SCHEMAS` in `agent/orchestrator.py` must stay in sync.
3. Did you change `_render()` in the orchestrator? The five-block `### 1.` through `### 5.` headers are checked.

### Alerts not dispatching in pre-shift run

Alerts only dispatch when `dispatch_alerts=True` is passed to the orchestrator. The pre-shift script does this automatically. The Wizard Chat tab does **not** dispatch alerts (queries are side-effect-free) — it only recommends them. This is by design.

### Feedback not affecting priority scores

By default, engineer feedback is re-indexed into RAG (so future diagnoses see the correction) but does **not** shift the priority score. This is controlled by the `MW_APPLY_FEEDBACK_BIAS` environment variable:

```powershell
$env:MW_APPLY_FEEDBACK_BIAS = "1"  # Enable score adjustment from feedback
```

This is intentionally off by default so the eval baseline stays reproducible.

---

## 7. Rollback steps

### Bad data generation

Re-run `python data/generate_mock_data.py`. This overwrites all CSVs and manuals. Then retrain the model and rebuild the RAG index.

### Bad model artifact

Delete and retrain:
```powershell
Remove-Item ml/artifacts/rul_model.pkl
Remove-Item ml/artifacts/feature_columns.json
python ml/train_model.py
```

### Corrupted RAG index

Delete and rebuild:
```powershell
Remove-Item -Recurse knowledge/store/
python knowledge/rag.py
```

### Full clean rebuild

```powershell
Remove-Item data/*.csv
Remove-Item -Recurse data/manuals/
Remove-Item -Recurse ml/artifacts/
Remove-Item -Recurse knowledge/store/
Remove-Item -Recurse reports/

python data/generate_mock_data.py
python ml/train_model.py
python knowledge/rag.py
```

---

## 8. Key files and directories

| Path | Purpose |
|---|---|
| `config.py` | Single source of truth: paths, thresholds, weights, baselines |
| `agent/orchestrator.py` | The "Consolidated Brain" — both execution modes |
| `agent/tools.py` | All tool implementations (pure, testable functions) |
| `agent/system_prompt.py` | LLM system prompt (five-block contract) |
| `app/streamlit_app.py` | The five-panel dashboard |
| `ml/model.py` | RUL model wrapper (sklearn or numpy fallback) |
| `ml/train_model.py` | Model training script |
| `knowledge/rag.py` | RAG index build + query (Chroma or TF-IDF) |
| `scripts/pre_shift_run.py` | Autonomous pre-shift briefing generator |
| `evals/judges.py` | Regression guard eval suite |
| `data/` | Generated CSVs, manuals, aliases |
| `ml/artifacts/` | Trained model pickle + feature columns |
| `knowledge/store/` | RAG vector store (Chroma DB or TF-IDF pickle) |
| `reports/` | Pre-shift briefing markdown files |

---

## 9. Escalation path

1. **Dashboard won't start** → Check Python version, pip dependencies, and that all pipeline steps ran
2. **Evals failing** → Check recent changes to `config.py`, `agent/tools.py`, or `agent/orchestrator.py`
3. **LLM mode issues** → Verify API key; system auto-falls back to deterministic mode
4. **Data looks wrong** → Re-run the full pipeline from `generate_mock_data.py`
5. **Persistent issues** → Check the git log for recent changes and consider reverting
