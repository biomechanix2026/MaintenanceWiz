# AI Hackathon — Agentic AI Challenge: Submission

## Title
Maintenance Wizard — an Agentic AI Decision-Support Copilot for Heavy Industry

## Theme
Agentic AI

## Demo Link
https://maintenancewiz.vercel.app

## Repository URL
https://github.com/biomechanix2026/MaintenanceWiz

## Description
Unplanned downtime in heavy industry costs millions per day, while the
knowledge needed to prevent it sits scattered across manuals, SOPs, delay
logs, incident records and ERP spares data. Maintenance Wizard is an
**agentic AI maintenance copilot** for a (synthetic) heavy steel plant that
fuses all five sources behind one conversation — and always answers in the
same auditable **five-block decision contract**: risk assessment, root-cause
breakdown, maintenance blueprint, supply-chain strategy, and a traceability
audit trail.

The agent is a single LLM tool-use loop (the "Consolidated Brain" — no
sub-agents) over **twelve tools**: fuzzy asset resolution (plant jargon →
asset ID), RUL prognostics with SHAP attribution, independent abnormality
detection, asset-filtered RAG over manuals/SOPs/incidents, ERP spares
lookup, transparent read-only SQL ("AI to build, UI to validate"), delay
history, deterministic risk scoring, role-routed alert dispatch, work-order
closure compliance, fault-mode classification, and an engineer feedback
loop that re-indexes corrections into retrieval.

What makes it agentic rather than a chatbot: the model decides which tools
to call and in what order, chains evidence across them (sensor deviation →
SHAP driver → SOP procedure → spares lead time), acts on the world
(alerts, closure checks, feedback writes), and obeys an explicit guardrail:
tool outputs are the only source of truth — torque values, part numbers and
isolation steps are never invented. Its signature behavior is
**constraint-aware planning**: when an out-of-stock part's lead time exceeds
the predicted remaining useful life, the recommendation flips from "replace
now" to a monitored-degradation strategy, because the part physically
cannot arrive before failure.

Two builds share the same data and tool contracts: the **full local build**
runs Claude with prompt caching and sentence-level citations, with a fully
deterministic offline fallback (the same tools in pipeline order) that
doubles as the reproducible baseline for the eval judges; the **hosted
demo** is a slim serverless build on Gemini 2.5 Flash (free tier) exposing
10 of the 12 tools over a precomputed prognostics snapshot, BM25 retrieval
and bundled read-only SQLite — so the public link costs nothing to operate
(with automatic degradation to Flash-Lite under free-tier load). All demo
assets are exported from the real implementation by one script, so the two
builds cannot drift.

All plant data is synthetic. Outputs are decision support requiring
engineer sign-off.

## Instructions to Run

### Hosted demo (no setup)
Open the demo link and ask e.g. "What's wrong with the mill gearbox?" — or
use plant jargon like "check the EAF". The agent runs several tool calls
per answer (typically 10–30 s). Free-tier rate limits apply (the UI
explains retries).

### Full local build
1. `pip install -r requirements.txt`  (the system also runs on
   numpy+pandas+streamlit alone via built-in fallbacks)
2. `python data/generate_mock_data.py`   # synthetic plant data + manuals
3. `python ml/train_model.py`            # RUL model artifact
4. `python knowledge/rag.py`             # RAG index (Chroma or TF-IDF)
5. `streamlit run app/streamlit_app.py`  # 5-panel dashboard
6. Optional: `ANTHROPIC_API_KEY` in `.env` switches the agent from the
   deterministic pipeline to the Claude tool-use loop (same tools, same
   five-block contract).
7. `python -m evals.judges` runs the regression evals;
   `python -m evals.demo_tests` covers the hosted-demo build.
8. Hosted build deploy: `cd web && vercel deploy --prod` with a
   `GEMINI_API_KEY` project env var (see `web/pyproject.toml` for the
   entrypoint config).

## Video URL (optional)
90-second walkthrough script:
1. (0:00) Problem: one sentence over the architecture slide.
2. (0:10) Open the demo, click "What's wrong with the mill gearbox?".
3. (0:25) While it thinks, narrate the tools it is calling.
4. (0:40) Show the five-block answer; zoom on the constraint flag — the
   pinion's 45-day lead time exceeds the predicted RUL, so the agent
   switches to monitored degradation instead of "replace now".
5. (1:00) Follow-up: "that valve that keeps leaking on the caster" —
   jargon-to-asset resolution.
6. (1:15) Mention the full Claude build: citations + deterministic
   offline fallback + eval judges.
7. (1:25) Close: synthetic-data caveat + repo link.
