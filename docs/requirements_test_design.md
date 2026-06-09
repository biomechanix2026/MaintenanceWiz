# Maintenance Wizard Requirement Test Design

Source requirement document: `document_pdf.pdf`  
Scope: design tests for the problem statement requirements without changing production behavior.

## Testing Approach

The project has no general test runner today; `python -m evals.judges` is the current regression guard. These tests should therefore be implemented as small Python modules under `evals/` and kept behavior-focused:

- Use `run_deterministic()` for end-to-end agent behavior so tests remain reproducible without API keys.
- Use pure tool tests for contracts in `agent/tools.py`.
- Use temporary files or monkeypatched config paths for tests that write feedback, logbook entries, alerts, or reports.
- Avoid exact prose matching. Assert structured fields, trace entries, five output blocks, source IDs, SQL echoing, and risk bands.
- For LLM-only behavior, test the schema and prompt contracts locally, then run a separate smoke test only when `ANTHROPIC_API_KEY` is present.

## Proposed Test Files

- `evals/requirement_judges.py`: problem-statement integration judges using `run_deterministic()`.
- `evals/tool_contract_tests.py`: direct tests for resolver, RAG, SQL, prognostics, abnormality, risk, feedback, alerting, and closure tools.
- `evals/reporting_tests.py`: pre-shift report, digital logbook, alert file, and deliverable/static checks.
- `evals/ui_manual_checklist.md`: Streamlit-only checks that require visual/manual inspection.

## Functional Requirements

| ID | Requirement | Test Design | Acceptance Criteria |
|---|---|---|---|
| FR-01 | Contextual reasoning using LLMs or SLMs | Run `run_agent("what's wrong with the mill gearbox?")` with no API key and verify deterministic fallback. Separately inspect `TOOL_SCHEMAS`, `SYSTEM_PROMPT`, and `run_llm()` when `ANTHROPIC_API_KEY` is set. | Offline mode returns an `AgentResult` with five blocks, structured output, and a tool trace. LLM mode exposes all tools in `TOOL_SCHEMAS` and keeps the same result contract. |
| FR-02 | Integrate manuals, SOPs, historical maintenance records, failure reports, and operational logs | Query `rag_tool()` for a known asset and assert returned chunks include `manual`, `incident`, and `delay_log` types filtered to the requested `asset_id`. | Every result has the requested `asset_id`. At least one SOP/manual source and one historical incident or delay-log source are returned for demo assets. |
| FR-03 | Natural language queries and context-aware multi-turn conversation | First call `run_deterministic("what's wrong with the mill gearbox?")`, then call `run_deterministic("what about its bearings?", focus_asset=first.asset_id)`. Add an ambiguous query test. | Follow-up uses the prior `focus_asset`; trace records conversation focus fallback. Ambiguous input returns clarification with candidate assets instead of inventing an asset. |
| FR-04 | Explainable and traceable recommendations | Run a critical gearbox query and inspect answer, trace, and structured payload. | Answer contains all five mandated blocks, SHAP/top-driver evidence, abnormality evidence, SOP/incident source names, and the exact SQL query. Trace includes each tool used to produce the recommendation. |
| FR-05 | Dynamic abnormality detection, early warning, and failure prediction | Call `abnormality_tool()` and `prognostic_tool()` for representative normal, warning, and critical assets. | Abnormality status is one of `NORMAL`, `WARNING`, `CRITICAL`; early warning is true for abnormal states; critical high-impact assets set `catastrophic_risk`; prognostic output includes RUL and 30-day failure probability. |
| FR-06 | Feedback-driven improvement | In a temp data sandbox, call `record_feedback()` with a correction and severity adjustment, then query `learned_bias()` and `rag_tool()` after reindex. | Feedback row is persisted, feedback count increases, learned adjustment is available, and a same-asset RAG query can retrieve feedback context. Priority score changes only when `MW_APPLY_FEEDBACK_BIAS=1`. |
| FR-07 | Real-time abnormal alert reports and user-specific notifications | Test `alert_dispatch_tool()` with `dry_run=True` and `dry_run=False` in a temp data directory. Run `run_deterministic(..., dispatch_alerts=False)` and `dispatch_alerts=True` for a critical asset. | Dry-run does not write notifications. Live dispatch writes one notification and dedupes same asset/band/day. Diagnostic queries recommend alerts without side effects; opted-in runs dispatch. |

## Expected Inputs

| ID | Input Requirement | Test Design | Acceptance Criteria |
|---|---|---|---|
| IN-01 | Equipment delay logs | `delay_history_tool("GEARBOX-05")` and SQL over `delays`. | Non-empty event count, downtime, tonnage loss, and top causes for assets with delay history. |
| IN-02 | Fault or error messages | Natural-language query containing symptoms, e.g. "gearbox vibration alarm". | Resolver maps to the correct asset or asks for clarification; downstream answer cites sensor/incident evidence. |
| IN-03 | Failure analysis reports | RAG query for known incident terms. | Incident chunks include incident ID, title, root cause, and resolution. |
| IN-04 | Incident records and breakdown summaries | `rag_tool(..., type incident)` via query and `sql_query_tool()` over `incidents`. | Incident data is retrievable and asset-filtered. |
| IN-05 | Sensor data summaries | `prognostic_tool()` and `abnormality_tool()` for every asset in registry. | Each known asset returns latest readings for all `SENSOR_FEATURES`. |
| IN-06 | Abnormality or anomaly alerts | `abnormality_tool()` for assets with known abnormal data. | Output includes status, anomaly score, breached features or trend features, thresholds, and recommendation. |
| IN-07 | Process condition indicators | Assert prognostic/abnormality outputs use all configured sensor features in order. | No missing sensor feature; output deviations are keyed by `SENSOR_FEATURES`. |
| IN-08 | Equipment manuals | `rag_tool("isolation repair", asset_id=...)`. | At least one manual/SOP section is returned for assets with manual files. |
| IN-09 | Maintenance SOPs | End-to-end answer block 3 for a known asset. | Isolation or repair steps are sourced from a manual/SOP chunk, not invented prose. |
| IN-10 | Historical maintenance records | Feedback and incident records are included in RAG build chunks. | Historical incident and engineer feedback chunks can be retrieved by asset. |
| IN-11 | Spare parts availability and procurement lead time | `inventory_tool()` and `risk_score_tool()` for `GEARBOX-05`. | Inventory includes quantity, status, lead time, and cost; risk sets `constraint_flag` when lead time exceeds RUL. |
| IN-12 | Natural language user queries | `run_deterministic()` with demo prompts from README. | Correct asset resolution and five-block response for known demo scenarios. |
| IN-13 | Scenario-based learning or troubleshooting prompts | Query using a scenario, then record feedback correction. | Scenario resolves to an asset and feedback persists as learning context. |
| IN-14 | Follow-up multi-turn queries | `focus_asset` follow-up test from FR-03. | Follow-up query uses prior asset when the query lacks an explicit asset. |

## Expected Outputs

| ID | Output Requirement | Test Design | Acceptance Criteria |
|---|---|---|---|
| OUT-01 | Probable fault diagnosis | End-to-end known incident query. | Block 2 includes probable fault from incident or manual source. |
| OUT-02 | Root cause analysis | RAG incident retrieval and answer block 2. | Root cause is tied to retrieved incident/manual evidence. |
| OUT-03 | Remaining lifecycle/RUL prediction | `prognostic_tool()` and full answer block 1. | RUL is numeric and appears in structured output and answer. |
| OUT-04 | Early warning of catastrophic failure | Critical abnormality test. | `early_warning=True` and `catastrophic_risk=True` for critical high-impact abnormal assets. |
| OUT-05 | Process-related defects contributing to equipment issues | Abnormality breached feature test. | Breached/trending sensor features identify contributing process condition evidence. |
| OUT-06 | Risk level classification | `risk_score_tool()` over all registry assets. | Every asset has score 0-100 and band in `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| OUT-07 | Urgency assessment | End-to-end critical and healthy scenarios. | Critical scenario recommends alert or urgent action; healthy scenario remains low/medium and no constraint. |
| OUT-08 | Plant-level bottleneck prioritization | Recreate `plant_scan()` behavior in a non-UI test. | Assets sort descending by priority score and include anomaly/constraint indicators. |
| OUT-09 | Prioritization by criticality, delay severity, spares, and lead time | Inspect `risk_score_tool()["components"]` and constraint flag. | Component scores exist for RUL, criticality, delay, and spares; constraint flag includes lead time vs RUL. |
| OUT-10 | Step-by-step maintenance or repair recommendations | Block 3 SOP extraction test. | Output includes ordered isolation steps or explicit manual fallback with source name. |
| OUT-11 | Immediate action points | Critical scenario output test. | Block 3 contains immediate isolation/inspection action for critical assets. |
| OUT-12 | Optimized maintenance plan | Constraint scenario output test. | If lead time exceeds RUL, recommendation switches to monitored degradation instead of simple replace-now. |
| OUT-13 | Long-term monitoring recommendations | Constraint and warning abnormality scenarios. | Output mentions increased monitoring, tightened alarms, or follow-up schedule as applicable. |
| OUT-14 | Spare procurement strategy | Inventory/risk scenario output test. | Block 4 lists parts, stock status, lead times, and mitigation. |
| OUT-15 | Structured maintenance reports | `scripts.pre_shift_run.run()` in temp reports directory. | Markdown report is created with counts, action queue, RUL, abnormality, and drafted work order details. |
| OUT-16 | Abnormal alert reports | Alert dispatch and pre-shift tests. | Notification record contains timestamp, asset, risk level, summary, and recipients. |
| OUT-17 | Decision summaries for engineers and supervisors | End-to-end answer contract test. | Five-block answer is concise, structured, and includes risk, diagnosis, action, logistics, and traceability. |
| OUT-18 | Equipment-specific digital maintenance log entries | `append_logbook()` and `task_closure_tool()` in temp data sandbox. | Closure is blocked until all checklist items are true; completed jobs append a row with work order and asset. |

## Optional Enhancements

| ID | Enhancement | Test Design | Acceptance Criteria |
|---|---|---|---|
| OE-01 | Conversational interface | Manual Streamlit checklist plus `run_agent()` history/focus test. | Chat preserves prior turns and asset focus. |
| OE-02 | Visualization dashboard | Manual Streamlit checklist for all five tabs. | Dashboard shows plant ranking, asset deep dive, chat, pre-shift report, and logbook. |
| OE-03 | Simulated IoT/equipment monitoring dashboard | Static/manual check of sensor-driven metrics and sliders. | Asset deep-dive displays live-like sensor summaries, SHAP chart, abnormality evidence, and recompute controls. |
| OE-04 | Dynamic knowledge base per equipment | Feedback reindex test. | New feedback becomes retrievable for the same asset without changing unrelated assets. |
| OE-05 | Automatic digital logbook | Logbook/closure test from OUT-18. | Jobs cannot close without required compliance items and completed entries persist. |
| OE-06 | User-role-based alerts and recommendations | Current system has recipient parameter but no role model. Design a negative coverage test. | Test should mark this as not implemented unless roles are added; existing alert accepts explicit recipients only. |

## Expected Outcomes

These are business outcomes, so tests should use observable proxies rather than claiming real plant impact.

| ID | Outcome | Test Design | Acceptance Criteria |
|---|---|---|---|
| EO-01 | Reduce unplanned downtime | Constraint and pre-shift tests. | High-risk assets appear in pre-shift action queue before manual query. |
| EO-02 | Improve maintenance response time | Pre-shift report generation test. | Report generation completes and creates drafted work-order text for every critical/high/abnormal asset. |
| EO-03 | Increase diagnostic accuracy | Regression judges for known scenarios. | Known demo scenarios resolve correct assets and expected risk/anomaly bands. |
| EO-04 | Shift from reactive to proactive maintenance | Abnormality and RUL tests. | Assets can be flagged from sensor/RUL evidence without requiring an incident query. |
| EO-05 | Improve planning and spare management | Inventory and constraint tests. | Out-of-stock long-lead parts are surfaced and alter the plan. |
| EO-06 | Enable faster informed troubleshooting | Traceability test. | Each answer includes source evidence and SQL for engineer validation. |

## Deliverables

| ID | Deliverable Requirement | Test Design | Acceptance Criteria |
|---|---|---|---|
| DL-01 | Detailed source code of a working prototype | Static smoke test over required paths plus `python -m evals.judges`. | Required modules/data artifacts exist and current eval judges pass. |
| DL-02 | Architecture, technology stack, data flow, model design, reasoning pipeline, alerting/prediction logic, assumptions, and limitations documentation | Static documentation test over `README.md`, `AGENTS.md`, and deck docs. | Required headings/topics are present, or the test reports missing documentation sections. |
| DL-03 | Install/configure/run documentation | Static README command check. | README includes setup, data generation, model training, RAG build, app run, and eval commands. |
| DL-04 | Sample input and output demonstration | Demo scenario test using README prompts. | Each sample input produces an answer with five blocks and a trace. |
| DL-05 | Screen recording showcasing built features | Manual submission checklist. | Recording file or external submission artifact is present before final packaging. |
| DL-06 | Single ZIP upload package | Packaging checklist. | Zip contains code, documentation, sample outputs, and screen recording; excludes transient caches and secrets. |

## TDD Notes For Implementation

For every automated test above:

1. Write the smallest test for one requirement.
2. Run it and confirm it fails for the expected reason if the behavior is missing.
3. Add or adjust production code only after the failing test is proven.
4. Re-run the focused test and then `python -m evals.judges`.

Do not bundle missing features into the same change as test scaffolding. Tests that document current gaps, such as role-based alerts or screen-recording packaging, should initially be marked as expected failures or checklist items until those features are implemented.
