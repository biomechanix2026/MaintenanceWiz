# 🛠️ Maintenance Wizard

An autonomous, context-aware **Industrial Decision-Support agent** for a heavy
steel manufacturing plant. It collapses five fragmented data sources — live
sensors, equipment manuals/SOPs, historical delay logs, failure-analysis
records and ERP spares inventory — into one **traceable, constraint-aware
maintenance decision** in seconds.

Built for the Agentic AI Challenge (Round 2). It is not a chatbot over manuals;
it is a **System of Action** that reasons about what is about to break, prepares
the work order before the engineer logs in, and refuses to close a job until
every compliance step is logged.

> 🧭 **Start here for the demo:** [User journeys & demo script](docs/UX_JOURNEYS.md) —
> how four plant roles use the Wizard, with timed, click-by-click walkthroughs.

## Hosted demo

Live demo (slim serverless build, Gemini 2.5 Flash free tier):
**https://maintenancewiz.vercel.app** — see `web/`. It exposes 10 of the
12 tools over a precomputed prognostics snapshot, BM25 retrieval and
bundled read-only SQLite, all exported from the real implementation by
`scripts/build_demo_assets.py`. The full build (Claude tool-use loop +
deterministic fallback) runs locally per the instructions below.

---

## The idea in one line

> Steel plants run **Systems of Record** — databases that tell you what broke
> and when. This is a **System of Action** — an agent that predicts what will
> break, prepares the fix, and closes the loop.

---

## Architecture

```
            SYSTEMS OF RECORD (passive)            ENGINEER INTERFACE (trust)
   asset registry · manuals · delay logs ·     Streamlit: inspect · validate ·
   incidents · ERP spares                       riff · correct · collaborate
                       \                              /
                        \                            /
                 ┌───────────────────────────────────────┐
                 │   CONSOLIDATED BRAIN  (action layer)    │
                 │   single think→act→observe loop,        │
                 │   full tool suite, no sub-agents        │
                 └───────────────────────────────────────┘
                 /          |            |           \
        Asset resolver  Prognostic ML  RAG (asset-   ERP / SQL /
        (fuzzy match)   RUL+SHAP        filtered)     alert / closure
```

**Why "Consolidated Brain"?** Following the Omni/Blobby lesson, planning is *not*
split between an outer agent and sub-agents (which causes "split-brain" knowledge
mismatches). One loop holds the full context and the entire tool suite.

**Smart tools, not string tools.** Every tool returns a rich structured object:
the ML tool returns RUL + failure probability + SHAP attribution; the independent
abnormality tool returns sensor-deviation and trend evidence; the RAG tool returns
SOP sections tagged to the exact asset; the ERP tool returns stock + lead time;
the SQL tool returns the *exact SQL it ran* so engineers can validate it. This is
the "AI to build, UI to validate" philosophy.

---

## Runs anywhere: production stack + zero-dependency fallback

Every layer has a fallback so the project runs with **only numpy + pandas +
streamlit**, and upgrades automatically when the production libraries are present:

| Layer | Production path | Fallback (no extra deps) |
|---|---|---|
| Prognostics | scikit-learn `RandomForestRegressor` | pure-numpy bagged tree ensemble |
| Explainability | `shap.TreeExplainer` | model-agnostic ablation attribution |
| Abnormality detection | sensor z-score + trend detector | same deterministic rule |
| Retrieval | ChromaDB + BM25 hybrid (RRF) | TF-IDF + BM25 hybrid (numpy/stdlib) |
| Reasoning | Claude tool-use loop (`ANTHROPIC_API_KEY`) | deterministic Python pipeline |

The deterministic pipeline is also the **reproducible baseline for the eval
judges** — the same fixed inputs must always land in the same risk band.

---

## Quick start

```bash
# 1. (optional) full stack — works without it too
pip install -r requirements.txt

# 2. build data + train model + index (idempotent)
python data/generate_mock_data.py
python ml/train_model.py
python knowledge/rag.py

# 3. run the dashboard
streamlit run app/streamlit_app.py

# optional: enable Claude reasoning mode
export ANTHROPIC_API_KEY=sk-ant-...
```

Other entry points:

```bash
python -m agent.orchestrator     # CLI demo of the 5-block output
python -m scripts.pre_shift_run  # autonomous pre-shift briefing (schedulable)
python -m evals.judges           # run the eval judges
```

---

## The five-block output contract

Every diagnosis returns exactly five scannable blocks:

1. **Operational Risk Assessment** — band, priority score, delay severity
2. **Diagnostic & Root-Cause Breakdown** — probable fault, SHAP drivers
3. **Actionable Maintenance Blueprint** — isolation steps, verified SOP tasks, long-term plan
4. **Supply-Chain Logistics Strategy** — spares status, lead-time mitigations
5. **Traceability & Audit Trail** — source manuals/sections, incident IDs, the SQL run

---

## Demo scenarios (each shows a different capability)

| Scenario | Try in Wizard Chat | What it proves |
|---|---|---|
| **Constraint-aware triage** | *what's wrong with the mill gearbox?* | GEARBOX-05 is CRITICAL; pinion lead (45d) **exceeds** RUL (~38d) → the agent switches from "replace now" to a monitored-degradation plan and recommends an alert. |
| **Independent abnormality detection** | *air compressor status* | Flags sensor deviations/trend separately from the RUL model, giving an early warning before risk scoring alone escalates. |
| **Fuzzy resolution** | *that valve that keeps leaking on the caster* | Maps plant jargon → `HYD-VALVE-07` before any tool call. |
| **Abbreviation** | *check the EAF* | Resolves to `FURNACE-01`. |
| **Pre-shift autonomy** | Pre-Shift Report tab | Work orders drafted for every flagged asset before anyone logs in. |
| **Loop closure** | Digital Logbook tab | Job closure is **blocked** until all five compliance items are green. |

---

## Priority scoring (deterministic, Step 4)

`Priority = 100 × (0.40·RUL + 0.30·criticality + 0.15·delay-history + 0.15·spares)`

A **constraint flag** fires when the longest lead time of an out-of-stock part
exceeds the predicted RUL — i.e. the repair physically cannot complete before
failure, so immediate scheduling is the wrong call.

---

## Abnormality detection

`abnormality_tool` runs independently of the RUL regressor. It compares the
latest sensor window against the `config.py` NOMINAL baselines, checks short-window
trend, and emits `NORMAL` / `WARNING` / `CRITICAL` with breached features and
thresholds. This keeps early-warning detection distinct from the RUL-derived
failure probability.

---

## Project layout

```
config.py                 single source of truth (paths, baselines, thresholds, weights)
data/
  generate_mock_data.py   asset-tagged CSVs + aliases + per-asset SOP markdown
  *.csv, manuals/         the Systems of Record
ml/
  model.py                RULModel (sklearn RF or numpy forest) + SHAP/ablation
  train_model.py          trains + saves ml/artifacts/rul_model.pkl
knowledge/
  rag.py                  asset-filtered hybrid RAG (ChromaDB/TF-IDF + BM25)
agent/
  system_prompt.py        the Consolidated-Brain system prompt
  tools.py                the 12-tool suite (structured outputs)
  orchestrator.py         think→act→observe loop (LLM + deterministic)
app/streamlit_app.py      5-panel dashboard
scripts/pre_shift_run.py  autonomous pre-shift briefing (cron-friendly)
evals/judges.py           observability-driven eval judges
```

---

## Mapping to the reference architectures

- **Omni / Blobby:** consolidated brain, semantic layer (asset registry +
  aliases), transparent SQL, interactive workbook (Deep-Dive sliders),
  feedback loop (logbook notes re-indexed), trace-based evals.
- **ForeSight:** Random Forest RUL, SHAP explainability, five specialized tools,
  think→act→observe loop, risk-based prioritization, email/alert dispatch,
  serialized `.pkl` model artifact.
- **Systems of Action:** proactive pre-shift run, collaborative multi-turn
  diagnosis, and compliance loop-closure that blocks incomplete jobs.

---

## Assumptions

- **Synthetic data.** All five sources are generated by `data/generate_mock_data.py`
  with a fixed seed (reproducible). Sensor "live" readings are the last rows of a
  static log, not a real stream; timestamps are frozen at generation time.
- **Healthy baselines are known.** `NOMINAL` per-asset-type means/stds in
  `config.py` are treated as ground truth; RUL/SHAP and abnormality z-scores are
  all relative to them.
- **One model across asset types.** A single RUL model serves every type because
  it trains on per-type *deviations*; this assumes the deviation framing
  generalises across furnaces, pumps, valves, etc.
- **Failure probability is a monotone transform of RUL**, not a separately
  trained classifier — directionally useful, not a calibrated probability.
- **Priority weights and thresholds are expert-set** (`RISK_WEIGHTS`,
  `PRIORITY_BANDS`, `ALERT_THRESHOLD`, `ANOMALY_*`), not learned.
- **Benchmark provenance.** The RUL estimator class is benchmarked on NASA
  C-MAPSS FD001 (`python -m ml.benchmark_rul`; RMSE recorded in
  `ml/artifacts/benchmark.json`) and the fault classifier on AI4I 2020
  (UCI 601, CC-BY 4.0). Both are analogues for steel-plant equipment:
  capability evidence, not validated plant predictions. C-MAPSS: Saxena &
  Goebel (2008), NASA Prognostics CoE.
- **The in-memory SQL DB is read-only demo data** rebuilt from the CSVs per
  process; queries cannot mutate it.

## Limitations

- **Demo scale.** ~12 assets and small corpora; the TF-IDF fallback is lexical,
  and `Database.run` caps fetched rows. Not load- or concurrency-tested.
- **No real-time ingestion.** Telemetry is replayed from CSV; there is no live
  IoT feed or streaming anomaly pipeline.
- **Feedback learning is deliberately conservative.** Engineer feedback always
  re-indexes into RAG (advisory), but it only adjusts `priority_score` when
  `MW_APPLY_FEEDBACK_BIAS=1`; there is no automated model retraining loop.
- **Role-based routing is severity-based** (OE-06): alerts route to
  maintenance/reliability/supervisor by band; there is no per-user identity,
  authentication, or notification-channel integration (email/SMS are mocked to
  a JSONL log).
- **LLM mode requires `ANTHROPIC_API_KEY`** and network access; without it the
  system runs the deterministic pipeline, which is the reproducible baseline but
  not identical prose.
- **Plant cascade reasoning is additive.** `cascade_tool` computes blast radius
  and `system_priority` on top of (never inside) the eval-judged
  `priority_score`; the topology spec lives in `config.py`
  (design: `docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`).
- **Not safety-certified.** Outputs are decision *support*; every recommendation
  must be validated by a qualified engineer against the cited SOPs.
