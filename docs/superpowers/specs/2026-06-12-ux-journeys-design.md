# UX Scenarios & User Journeys — Design Spec

**Date:** 2026-06-12
**Status:** Approved pending user review
**Component of:** Maintenance Wizard (Agentic AI Challenge Round 2 submission)
**Companions:** `docs/UIUX_SPEC.md` (personas, surfaces), `docs/FEATURE_RESEARCH.md` (feature priorities), `docs/deck/` (pitch deck), `docs/ARCHITECTURE_DESIGN.md` §2 (PDF requirement traceability)

## 1. Purpose

Two goals, one artifact:

1. **Explain the software to judges** through persona-led journeys that double as the
   timed demo/video script — every Part-1 step is a real click on a real screen.
2. **Drive feature planning** through to-be journeys whose gap tables convert
   narrative friction into named, linked feature candidates.

## 2. Approved decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Today vs vision | **Both, clearly separated** — Part 1 "today" (demo-grade), Part 2 "to-be" (ROADMAP-labeled) |
| 2 | Personas | **Four** — field technician, shift supervisor, reliability engineer (from `UIUX_SPEC.md`) + **maintenance manager** (new; carries the IW38/logs/signoff story) |
| 3 | Format | **Markdown doc + deck hooks** — `docs/UX_JOURNEYS.md`, linked from README; deck-slide candidates listed, slide edits out of scope |
| 4 | Judge mode | **Live demo / video** — each Part-1 journey carries a timed click-by-click script |
| 5 | Structure | **Approach 1 + drama** — persona-led day-in-the-life, each journey pinned to an incident seeded in the mock data, opening with a one-sentence cold open |
| 6 | Visuals | **Generated SVGs interspersed with narrative + real app screenshots in Part 1** |

## 3. The artifact

- `docs/UX_JOURNEYS.md` — the document. README gains a link near the conceptual
  framing section.
- `docs/journeys/` — all visual assets (SVGs authored in the deck's visual
  language; PNG screenshots captured from the running app).

## 4. Journey template (identical anatomy for all six)

1. **Cold open** — the incident in one dramatic sentence.
2. **Journey map strip** (SVG) — horizontal step timeline: persona action above
   the line, system/tool response below, screens as chips, the
   "moment that matters" highlighted.
3. **The journey** — numbered narrative steps: persona action → screen/tab →
   what the system does (real tool names) → what they see. Screenshots
   interspersed at key moments (Part 1 only).
4. **What to notice** — judge callouts pinned to step numbers: trace expander,
   SQL echo, five-block contract, constraint flip, side-effect gating,
   mode badge (offline-capable).
5. **Demo script** — timed (mm:ss), exact query strings, expected on-screen
   results. Doubles as the video storyboard.
6. **Traceability line** — PDF objectives demonstrated (mirrors
   `ARCHITECTURE_DESIGN.md` §2 numbering).
7. *(Part 2 only)* **Gap table** — see §7.

## 5. The six journeys

### Part 1 — Today (each pinned to a seeded incident; verified against the app)

| ID | Persona | Cold-open incident | Spine | Moment that matters | Target time |
|----|---------|--------------------|-------|---------------------|-------------|
| T1 | Field technician | GEARBOX-05 vibration climbing; replacement pinion is 45 days away | Chat query ("what's wrong with the mill gearbox?") → five-block answer cards → isolation steps from SOP-GBX-05 → logbook closure blocked by checklist → close | **Constraint flip:** PINION-G5 lead 45d > RUL → plan becomes monitored degradation | 2:30 |
| T2 | Shift supervisor | It's 06:00; nobody has logged in yet, and the night produced new risk | `python -m scripts.pre_shift_run` → `reports/preshift_*.md` → role-routed, deduped alerts → wallboard (`?wallboard=1`) → handover | **Systems of Action:** drafted work orders and routed alerts exist before the first human login | 1:30 |
| T3 | Reliability engineer | The Wizard blamed a bearing on PUMP-12 — the engineer knows it's the seal | Read diagnosis → Logbook "Teach the Wizard": correction + outcome + severity slider → re-run the same query | **The learning loop closes on camera:** the new answer cites the engineer's own words; the honesty caption states the score is unaffected unless calibration mode is on | 2:00 |
| T4 | Maintenance manager | Monday standup: "where is tomorrow's downtime coming from?" | Bottleneck board (cards, bands, ⚠️ constraint chips) → deep-dive evidence room → SQL echo validation in chat | **Evidence on demand:** every headline number traces to a tool output in two clicks | 1:30 |

Total Part-1 demo: **7:30** + a 30-second Part-2 vision teaser (F1 storyboard) = ~8:00.

**In-flight tranche tagging:** T4 steps that depend on the approved-but-unexecuted
cascade/scenario/KPI plan (topology graph, `system_priority`, KPI cards,
what-if deferral slider) appear inline tagged **🔜 in-flight** with a footnote
naming the plan. When the tranche lands, the tags are deleted — the doc
upgrades without restructuring.

### Part 2 — To-be (ROADMAP-labeled; the planning payload)

| ID | Persona | Cold-open incident | Spine |
|----|---------|--------------------|-------|
| F1 | Maintenance manager | Three systems of record before breakfast: IW38 in SAP, the HMI wall, and a Word file called `breakdowns_final_v7.docx` | Conversational morning briefing → IW38 order-list export ingested via the CSV adapter seam → "log a 40-min breakdown on belt 3, bearing noise" filed into the right table by intent → daily task list signoff → legacy Word/Excel logs ingested once into the corpus |
| F2 | Field technician | A coupling lets go mid-shift; the paperwork usually waits until the wrench is down | QR scan on the asset → mobile deep-dive → voice note breakdown capture → photo evidence attached → guided SOP checklist → end-of-shift signoff |

## 6. Truthfulness mechanics

Three visual states, used consistently:

- **Plain step** — runs today; a judge can click it during Q&A.
- **🔜 in-flight** — approved tranche, plan committed, not yet merged.
- **ROADMAP** — Part 2 only; banner on every F-journey page and sketch-toned
  visuals so concept frames cannot be mistaken for shipped UI.

Part 1 may not claim anything a live click or an eval cannot verify — the same
"tool outputs are the only source of truth" ethic the agent itself follows.

## 7. Gap tables (the feature-planning hook)

Each Part-2 journey ends with:

| Journey step | Missing today | Feature that closes it | Link | Effort |
|---|---|---|---|---|

Links point to `FEATURE_RESEARCH.md` sections where they exist (§3.5 governed
copilot, §3.8 HSE gates, §3.9 mobile-lite). Steps with no research entry are
flagged **NEW** and enumerated in a closing "additions for FEATURE_RESEARCH.md"
list. Known NEW candidates from F1/F2:

1. SAP IW38 order-list CSV adapter (maintenance + calibration orders)
2. Legacy document ingestion (Word/Excel breakdown logs → incidents/corpus)
3. Conversational intake intent router (breakdown / reading / order ref / closure → correct table)
4. User identity & signoff (named closure, daily management gate)
5. Daily management board (today's tasks, signoff state, exceptions)

## 8. Visual system

Style matches `docs/deck/architecture.svg` (palette, fonts, chip shapes) so the
repo presents one visual language. All assets in `docs/journeys/`:

| Asset | Type | Content |
|---|---|---|
| `cast.svg` | SVG | Four persona cards: surface, context, primary need |
| `t1_map.svg` … `t4_map.svg` | SVG | Journey map strips (template element 2) |
| `f1_map.svg`, `f2_map.svg` | SVG | Journey strips, sketch-toned ROADMAP styling |
| `f1_storyboard.svg`, `f2_storyboard.svg` | SVG | Concept frames: chat intake filing into tables; phone QR/voice/photo flow |
| `today_vs_tobe.svg` | SVG | Manager capability strip today vs to-be — the most deck-worthy single visual |
| `t1_fiveblock_constraint.png`, `t1_trace.png`, `t2_wallboard.png`, `t2_preshift.png`, `t3_feedback_cited.png`, `t4_board.png` | PNG | Real app screenshots, dark theme, captured during the verification walk |

Screenshots are captured at consistent window size during the demo-script
verification pass, so picture and script can never disagree.

## 9. Verification (definition of done)

1. Every Part-1 demo script walked click-by-click against the running app in
   **deterministic mode** (reproducible on judge machines, no API key).
2. Screenshots captured during that same walk — script and pixels match.
3. Traceability lines checked against `ARCHITECTURE_DESIGN.md` §2's PDF mapping.
4. Gap-table links resolve to real `FEATURE_RESEARCH.md` anchors; NEW items
   listed in the closing additions section.
5. Tag audit: no plain-state step describes anything not on `main`/current branch;
   🔜 only for the committed tranche plan; ROADMAP confined to Part 2.

**Note for the implementation plan:** the Streamlit UI is actively evolving
(wallboard mode, candidate chips, gated dispatch, five-block chat cards all
landed recently). Demo scripts must be authored against the *running app at
write time*, not against remembered or quoted UI code.

## 10. Deck hooks (listed, not executed)

Slide candidates, in pitch order: T1's constraint-flip moment (`t1_map.svg` +
`t1_fiveblock_constraint.png`), T2's before-login autonomy, `today_vs_tobe.svg`
as the vision slide, `cast.svg` as the personas slide. Slide edits in
`docs/deck/build_deck.js` are a separate task after the journeys land.

## 11. Out of scope (YAGNI)

- Deck slide implementation (hooks only).
- Building any Part-2 feature — F-journeys are planning instruments.
- Mermaid/auto-generated diagrams — all SVGs are authored for visual quality.
- Light-theme screenshot variants.
- Translations / localization of journey narratives.
