# Manual / Visual Checklist (non-automatable requirements)

These requirements need a human to launch the Streamlit app or inspect the
submission package; the automated suites cannot assert them. Run:

```bash
streamlit run app/streamlit_app.py
```

## Optional Enhancements

- [ ] **OE-01 Conversational interface** — Wizard Chat keeps prior turns; a
      follow-up like "what about its bearings?" stays on the previously
      diagnosed asset (multi-turn focus). *(Automated proxy: FR-03 / IN-14.)*
- [ ] **OE-02 Visualization dashboard** — all five tabs render: Plant
      Bottleneck, Asset Deep-Dive, Wizard Chat, Pre-Shift Report, Digital
      Logbook.
- [ ] **OE-03 Simulated IoT / monitoring** — Asset Deep-Dive shows live-like
      sensor summaries, the SHAP contribution chart, abnormality evidence, and
      the slider "workbook" recomputes RUL.
- [ ] **OE-05 Automatic digital logbook** — a job cannot be closed until all
      five compliance checkboxes are green; closing appends a logbook row.
      *(Automated proxy: OUT-18.)*

## Deliverables

- [ ] **DL-05 Screen recording** — a recording that showcases the built
      features exists and is included in the submission.
- [ ] **DL-06 Single ZIP package** — the submission zip contains code, docs
      (README, AGENTS, deck), sample outputs, and the screen recording; it
      EXCLUDES transient caches and secrets (`__pycache__/`, `.env`,
      `data/notifications.jsonl`, `data/feedback.csv`, `.superpowers/`,
      `docs/deck/slides/`). The repo `.gitignore` already lists these.

## Notes / known gaps surfaced by the automated suites

- **OE-06 user-role-based alerts** — not implemented; `alert_dispatch_tool`
  accepts an explicit `recipients` string but has no role model. (Reported as a
  GAP by `tool_contract_tests`.)
- **DL-02 documentation topics** — README is missing explicit **Assumptions**
  and **Limitations** sections. (Reported as a GAP by `reporting_tests`.)
