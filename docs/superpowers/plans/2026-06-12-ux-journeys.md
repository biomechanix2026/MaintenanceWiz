# UX Scenarios & User Journeys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/UX_JOURNEYS.md` + `docs/journeys/` assets per `docs/superpowers/specs/2026-06-12-ux-journeys-design.md` — four demo-grade "today" journeys with timed scripts and real screenshots, two ROADMAP journeys with gap tables, all visuals interspersed with narrative.

**Architecture:** Docs-only. Each journey is a self-contained section built from one template (cold open → SVG map → narrative → judge callouts → timed demo script → traceability). Ground truth is harvested from the running system before writing — every number in the doc is transcribed from tool output, never invented (the same grounding ethic as the agent). Screenshots are captured in one verification walk at the end so pixels and scripts cannot disagree.

**Tech Stack:** Markdown, hand-authored SVG, Streamlit app run read-only for verification, Python CLI entry points for ground truth.

**HARD CONSTRAINT (spec §11):** A frontend upgrade is in flight. **Never create, modify, or delete anything under `app/`.** If a demo script doesn't match the live UI, fix the script. Every task ends with `git status --short app/` → must print nothing. Every commit in this plan uses explicit pathspecs (`git commit -m "..." -- <paths>`) so in-flight staged work is never swept in.

**Runtime artifacts are not committed:** walks may dirty `data/feedback.csv`, `data/notifications.jsonl`, `knowledge/store/*`, `reports/*` — these are regenerable runtime files; leave them out of every commit.

**File structure (whole plan):**
- Create: `docs/UX_JOURNEYS.md` — the document
- Create: `docs/journeys/cast.svg`, `t1_map.svg`…`t4_map.svg`, `f1_map.svg`, `f2_map.svg`, `f1_storyboard.svg`, `f2_storyboard.svg`, `today_vs_tobe.svg`
- Create: `docs/journeys/t1_fiveblock_constraint.png`, `t1_trace.png`, `t2_wallboard.png`, `t2_preshift.png`, `t3_feedback_cited.png`, `t4_board.png` (Task 7)
- Modify: `README.md` — one link line

---

## Shared template (used verbatim by Tasks 2–6)

Every journey section in `docs/UX_JOURNEYS.md` has this exact shape:

````markdown
## <ID> · <Persona> — "<Journey title>"

> *<Cold open: the incident in one sentence.>*

![<ID> journey map](journeys/<id>_map.svg)

### The journey

1. **<Persona action>** — *<screen/tab>*. <What the system does (tool names) and what they see.>
2. …

### What to notice (judges)

- **Step <n>:** <differentiator callout>
- …

### Demo script (<target time>)

| Clock | Action | Expect on screen |
|---|---|---|
| 0:00 | … | … |

### Traceability

Demonstrates PDF objectives: <numbers per ARCHITECTURE_DESIGN.md §2>.
````

Part 2 journeys add a `### Gap table` and use the ROADMAP banner:
`> **ROADMAP — nothing in this journey is built yet.** It exists to drive planning; see the gap table.`

**Ground-truth tokens:** narrative drafts below use `«TOKEN»` markers. Each task's harvest step says exactly which command output fills each token. A `«TOKEN»` left in the committed doc is a task failure.

---

## Task 1: Skeleton, cast card, README link

**Files:**
- Create: `docs/UX_JOURNEYS.md`
- Create: `docs/journeys/cast.svg`
- Modify: `README.md`

- [ ] **Step 1: Create `docs/journeys/` and the document skeleton**

Create `docs/UX_JOURNEYS.md`:

````markdown
# Maintenance Wizard — User Journeys & Demo Script

> Four plant roles, six journeys. Part 1 is **real today** — every step is a click
> you can perform in the running app (deterministic mode, no API key needed), and
> each journey carries a timed demo script. Part 2 is **ROADMAP** — to-be journeys
> that drive our feature planning; nothing in Part 2 is built.

**How to read the tags:** plain step = runs today · 🔜 = approved tranche in
flight (`docs/superpowers/plans/2026-06-12-cascade-scenario-kpi.md`) · ROADMAP =
Part 2 only, not built.

![The cast](journeys/cast.svg)

| Persona | Surface | Lives in |
|---|---|---|
| **Arjun — Field technician** | Rugged tablet on the floor | Wizard Chat, Deep-Dive, Logbook |
| **Meera — Shift supervisor** | Control-room wallboard + laptop | Pre-Shift Report, wallboard, alerts |
| **Dev — Reliability engineer** | Laptop, desk + floor walks | Deep-Dive, Logbook feedback |
| **Shalini — Maintenance manager** | Laptop, morning standup | Bottleneck board, evidence room |

---

# Part 1 — Today (demo-grade)

<!-- T1..T4 inserted by Tasks 2-5 -->

---

# Part 2 — To-be (ROADMAP)

<!-- F1..F2 inserted by Task 6 -->

---

# Additions proposed for FEATURE_RESEARCH.md

<!-- filled by Task 6 -->

# Deck hooks

<!-- filled by Task 8 -->
````

- [ ] **Step 2: Create `docs/journeys/cast.svg`**

Four persona cards in the deck's visual language (light panels `#F8FAFC`, stroke `#94A3B8`, ink `#1F2937`, accent `#2563EB`, font Helvetica):

```xml
<svg viewBox="0 0 1200 240" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial,sans-serif">
  <text x="16" y="28" font-size="18" font-weight="bold" fill="#1F2937">The cast — four roles, one consolidated brain</text>
  <!-- card template: x = 16, 316, 616, 916 -->
  <g>
    <rect x="16" y="48" width="280" height="170" rx="10" fill="#F8FAFC" stroke="#94A3B8"/>
    <circle cx="52" cy="88" r="20" fill="#2563EB"/><text x="52" y="94" font-size="16" fill="#fff" text-anchor="middle">A</text>
    <text x="84" y="84" font-size="15" font-weight="bold" fill="#1F2937">Arjun</text>
    <text x="84" y="102" font-size="12" fill="#475569">Field technician</text>
    <text x="32" y="136" font-size="12" fill="#1F2937">Gloved, interrupted, on the floor.</text>
    <text x="32" y="156" font-size="12" fill="#1F2937">Needs: what to fix, in what order,</text>
    <text x="32" y="172" font-size="12" fill="#1F2937">with which steps and parts.</text>
    <text x="32" y="200" font-size="11" fill="#2563EB">Chat · Deep-Dive · Logbook</text>
  </g>
  <g>
    <rect x="316" y="48" width="280" height="170" rx="10" fill="#F8FAFC" stroke="#94A3B8"/>
    <circle cx="352" cy="88" r="20" fill="#0EA5E9"/><text x="352" y="94" font-size="16" fill="#fff" text-anchor="middle">M</text>
    <text x="384" y="84" font-size="15" font-weight="bold" fill="#1F2937">Meera</text>
    <text x="384" y="102" font-size="12" fill="#475569">Shift supervisor</text>
    <text x="332" y="136" font-size="12" fill="#1F2937">Control room, shift handover.</text>
    <text x="332" y="156" font-size="12" fill="#1F2937">Needs: plant-wide risk before</text>
    <text x="332" y="172" font-size="12" fill="#1F2937">anyone logs in.</text>
    <text x="332" y="200" font-size="11" fill="#2563EB">Pre-Shift · Wallboard · Alerts</text>
  </g>
  <g>
    <rect x="616" y="48" width="280" height="170" rx="10" fill="#F8FAFC" stroke="#94A3B8"/>
    <circle cx="652" cy="88" r="20" fill="#10B981"/><text x="652" y="94" font-size="16" fill="#fff" text-anchor="middle">D</text>
    <text x="684" y="84" font-size="15" font-weight="bold" fill="#1F2937">Dev</text>
    <text x="684" y="102" font-size="12" fill="#475569">Reliability engineer</text>
    <text x="632" y="136" font-size="12" fill="#1F2937">Desk + floor walks.</text>
    <text x="632" y="156" font-size="12" fill="#1F2937">Needs: why the score is what it is —</text>
    <text x="632" y="172" font-size="12" fill="#1F2937">and a way to correct the system.</text>
    <text x="632" y="200" font-size="11" fill="#2563EB">Deep-Dive · Feedback loop</text>
  </g>
  <g>
    <rect x="916" y="48" width="280" height="170" rx="10" fill="#F8FAFC" stroke="#94A3B8"/>
    <circle cx="952" cy="88" r="20" fill="#F59E0B"/><text x="952" y="94" font-size="16" fill="#fff" text-anchor="middle">S</text>
    <text x="984" y="84" font-size="15" font-weight="bold" fill="#1F2937">Shalini</text>
    <text x="984" y="102" font-size="12" fill="#475569">Maintenance manager</text>
    <text x="932" y="136" font-size="12" fill="#1F2937">Standups, IW38, daily management.</text>
    <text x="932" y="156" font-size="12" fill="#1F2937">Needs: where tomorrow's downtime</text>
    <text x="932" y="172" font-size="12" fill="#1F2937">comes from — with evidence.</text>
    <text x="932" y="200" font-size="11" fill="#2563EB">Bottleneck board · Evidence room</text>
  </g>
</svg>
```

- [ ] **Step 3: Add the README link**

In `README.md`, find the end of the opening section (the first paragraph block under the main title, before the first `##` heading) and insert:

```markdown
> 🧭 **Start here for the demo:** [User journeys & demo script](docs/UX_JOURNEYS.md) —
> how four plant roles use the Wizard, with timed, click-by-click walkthroughs.
```

- [ ] **Step 4: Verify and commit**

Run: `git status --short app/` → must print nothing.
Open `docs/UX_JOURNEYS.md` in a Markdown preview → cast.svg renders, table renders.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/cast.svg README.md
git commit -m "docs(journeys): skeleton, persona cast card, README entry point" -- docs/UX_JOURNEYS.md docs/journeys/cast.svg README.md
```

---

## Task 2: T1 — Technician, the constraint flip (GEARBOX-05)

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (replace `<!-- T1..T4 inserted by Tasks 2-5 -->` start)
- Create: `docs/journeys/t1_map.svg`

- [ ] **Step 1: Harvest ground truth**

Run: `python -m agent.orchestrator`
From the first query's output (`what's wrong with the mill gearbox?`) transcribe:
- `«RUL»` ← the "Remaining Useful Life" value in Block 1
- `«SCORE»`/`«BAND»` ← priority score/band in Block 1
- `«PROB»` ← 30-day failure probability
- `«DRIVER»` ← top SHAP driver in Block 2
- `«NTOOLS»` ← the `tools=` count in the `[mode=...]` line
- Confirm Block 4 shows `PINION-G5 … OUT` with 45d lead and Block 3 says "monitored degradation".

If any expectation fails (e.g., constraint absent), STOP — the seeded data changed; re-run `python data/generate_mock_data.py && python ml/train_model.py && python knowledge/rag.py` and harvest again.

- [ ] **Step 2: Write `docs/journeys/t1_map.svg`**

```xml
<svg viewBox="0 0 1200 320" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial,sans-serif">
  <text x="16" y="26" font-size="16" font-weight="bold" fill="#1F2937">T1 · Arjun, field technician — the part that can't arrive in time</text>
  <rect x="1020" y="8" width="164" height="24" rx="12" fill="#EAF2FB" stroke="#9CC0E6"/>
  <text x="1102" y="24" font-size="11" fill="#1F2937" text-anchor="middle">surface: Wizard Chat + Logbook</text>
  <line x1="40" y1="160" x2="1160" y2="160" stroke="#94A3B8" stroke-width="2"/>
  <!-- 6 steps at x-centers 130,310,490,670,850,1030; action above, system below -->
  <!-- step template -->
  <g><!-- 1 -->
    <circle cx="130" cy="160" r="6" fill="#2563EB"/>
    <rect x="50" y="60" width="160" height="72" rx="8" fill="#F8FAFC" stroke="#94A3B8"/>
    <text x="130" y="84" font-size="11" fill="#1F2937" text-anchor="middle">Asks in plain words:</text>
    <text x="130" y="100" font-size="11" font-style="italic" fill="#1F2937" text-anchor="middle">"what's wrong with</text>
    <text x="130" y="114" font-size="11" font-style="italic" fill="#1F2937" text-anchor="middle">the mill gearbox?"</text>
    <rect x="50" y="190" width="160" height="56" rx="8" fill="#EAF2FB" stroke="#9CC0E6"/>
    <text x="130" y="212" font-size="10" fill="#1F2937" text-anchor="middle">resolve_asset</text>
    <text x="130" y="228" font-size="10" fill="#1F2937" text-anchor="middle">→ GEARBOX-05</text>
  </g>
  <g><!-- 2 -->
    <circle cx="310" cy="160" r="6" fill="#2563EB"/>
    <rect x="230" y="60" width="160" height="72" rx="8" fill="#F8FAFC" stroke="#94A3B8"/>
    <text x="310" y="90" font-size="11" fill="#1F2937" text-anchor="middle">Reads risk + root cause</text>
    <text x="310" y="106" font-size="11" fill="#1F2937" text-anchor="middle">(five-block cards)</text>
    <rect x="230" y="190" width="160" height="56" rx="8" fill="#EAF2FB" stroke="#9CC0E6"/>
    <text x="310" y="212" font-size="10" fill="#1F2937" text-anchor="middle">prognostic + abnormality</text>
    <text x="310" y="228" font-size="10" fill="#1F2937" text-anchor="middle">+ asset-filtered RAG</text>
  </g>
  <g><!-- 3 -->
    <circle cx="490" cy="160" r="6" fill="#2563EB"/>
    <rect x="410" y="60" width="160" height="72" rx="8" fill="#F8FAFC" stroke="#94A3B8"/>
    <text x="490" y="90" font-size="11" fill="#1F2937" text-anchor="middle">Opens the trace:</text>
    <text x="490" y="106" font-size="11" fill="#1F2937" text-anchor="middle">every tool call + the SQL</text>
    <rect x="410" y="190" width="160" height="56" rx="8" fill="#EAF2FB" stroke="#9CC0E6"/>
    <text x="490" y="212" font-size="10" fill="#1F2937" text-anchor="middle">AgentResult.trace</text>
    <text x="490" y="228" font-size="10" fill="#1F2937" text-anchor="middle">"AI to build, UI to validate"</text>
  </g>
  <g><!-- 4 HIGHLIGHT -->
    <circle cx="670" cy="160" r="8" fill="#B388FF"/>
    <rect x="586" y="52" width="168" height="84" rx="8" fill="#F3E8FF" stroke="#B388FF" stroke-width="2"/>
    <text x="670" y="76" font-size="11" font-weight="bold" fill="#1F2937" text-anchor="middle">⛔ Sees: the part cannot</text>
    <text x="670" y="92" font-size="11" font-weight="bold" fill="#1F2937" text-anchor="middle">arrive before failure</text>
    <text x="670" y="112" font-size="10" fill="#6B21A8" text-anchor="middle">the moment that matters</text>
    <rect x="586" y="190" width="168" height="56" rx="8" fill="#F3E8FF" stroke="#B388FF"/>
    <text x="670" y="212" font-size="10" fill="#1F2937" text-anchor="middle">45d lead &gt; RUL → plan flips</text>
    <text x="670" y="228" font-size="10" fill="#1F2937" text-anchor="middle">to monitored degradation</text>
  </g>
  <g><!-- 5 -->
    <circle cx="850" cy="160" r="6" fill="#2563EB"/>
    <rect x="770" y="60" width="160" height="72" rx="8" fill="#F8FAFC" stroke="#94A3B8"/>
    <text x="850" y="90" font-size="11" fill="#1F2937" text-anchor="middle">Follows isolation steps</text>
    <text x="850" y="106" font-size="11" fill="#1F2937" text-anchor="middle">from the cited SOP</text>
    <rect x="770" y="190" width="160" height="56" rx="8" fill="#EAF2FB" stroke="#9CC0E6"/>
    <text x="850" y="212" font-size="10" fill="#1F2937" text-anchor="middle">Block 3 · SOP-GBX-05</text>
    <text x="850" y="228" font-size="10" fill="#1F2937" text-anchor="middle">nothing from memory</text>
  </g>
  <g><!-- 6 -->
    <circle cx="1030" cy="160" r="6" fill="#2563EB"/>
    <rect x="950" y="60" width="160" height="72" rx="8" fill="#F8FAFC" stroke="#94A3B8"/>
    <text x="1030" y="90" font-size="11" fill="#1F2937" text-anchor="middle">Closes the job — gate</text>
    <text x="1030" y="106" font-size="11" fill="#1F2937" text-anchor="middle">blocks until compliant</text>
    <rect x="950" y="190" width="160" height="56" rx="8" fill="#EAF2FB" stroke="#9CC0E6"/>
    <text x="1030" y="212" font-size="10" fill="#1F2937" text-anchor="middle">task_closure_tool</text>
    <text x="1030" y="228" font-size="10" fill="#1F2937" text-anchor="middle">→ digital logbook</text>
  </g>
</svg>
```

- [ ] **Step 3: Write the T1 section into `docs/UX_JOURNEYS.md`**

Insert under `# Part 1` (replacing the placeholder comment's first slot), using the shared template with this content; resolve every `«TOKEN»` from Step 1:

````markdown
## T1 · Arjun, field technician — "The part that can't arrive in time"

> *At shift start the mill drive gearbox is trending toward failure — and the
> replacement pinion is 45 days away.*

![T1 journey map](journeys/t1_map.svg)

### The journey

1. **Arjun types what he'd say to a colleague** — *Wizard Chat*: "what's wrong
   with the mill gearbox?" `resolve_asset` maps the jargon to **GEARBOX-05**.
2. **The answer arrives as five fixed blocks** — risk (**«BAND»**, «SCORE»/100,
   RUL **«RUL» days**, failure probability «PROB»), root cause (top driver
   **«DRIVER»**, matched against historical incident records), blueprint,
   logistics, audit trail. Same contract every time, both engine modes.

![Five-block answer with constraint chip](journeys/t1_fiveblock_constraint.png)

3. **He opens "how I got this"** — the trace expander lists all «NTOOLS» tool
   calls with inputs and outputs, including the exact SQL the agent ran.

![The tool trace](journeys/t1_trace.png)

4. **⛔ The flip** — Block 4 shows the drive pinion `PINION-G5` is **out of
   stock with a 45-day lead** — longer than the «RUL»-day RUL. The Wizard
   doesn't say "replace now" anyway; the recommendation flips to **monitored
   degradation**: tightened alarms, interim mitigation, expedited procurement.
5. **He works the isolation steps** — Block 3 lists them from **SOP-GBX-05**,
   cited by name. Torque values and steps come only from tool outputs — never
   from model memory.
6. **He closes the work order** — *Digital Logbook*: the closure button stays
   disabled until the compliance checklist (parts recorded, steps logged,
   isolation cleared, follow-up scheduled, logbook entry) is green.

### What to notice (judges)

- **Step 2:** the five-block contract is identical in LLM and offline
  deterministic mode — run this demo with no API key.
- **Step 3:** observability as UX — every number traces to a tool output.
- **Step 4:** constraint-aware reasoning, not lookup: lead time vs RUL changes
  the *recommendation class*.
- **Step 6:** chat never writes; closure goes through a gated form. Side
  effects are opt-in by design.

### Demo script (2:30)

| Clock | Action | Expect on screen |
|---|---|---|
| 0:00 | Open the app; point at the engine-mode badge | "Deterministic (offline)" or "LLM" |
| 0:10 | Chat tab → type *what's wrong with the mill gearbox?* | Five block-cards render |
| 0:30 | Read Block 1 aloud | «BAND» · «SCORE»/100 · RUL «RUL»d |
| 0:50 | Expand the tool trace | «NTOOLS» calls; SQL in a code block |
| 1:10 | Point at Block 4 part rows | PINION-G5 OUT, 45d lead |
| 1:25 | Read the flip line in Block 3 | "monitored degradation" |
| 1:45 | Logbook tab → tick checklist items one by one | Button enables only at 5/5 |
| 2:15 | Close & log | Logbook entry appears |

### Traceability

Demonstrates PDF objectives: 4.3 (manuals/spares), 4.4 (NL queries), 5.1
(diagnosis, root cause, RUL), 5.2 (constraint-based priority), 5.3 (step-by-step
actions, procurement strategy), 5.4 (digital log), 6.4 (explainability).
````

(The two `![…](journeys/*.png)` images will 404 in preview until Task 7 captures them — acceptable; Task 7 closes the loop.)

- [ ] **Step 4: Verify and commit**

Check: no `«` character remains in the T1 section (`Select-String -Path docs/UX_JOURNEYS.md -Pattern "«"` → only matches in not-yet-written sections, none in T1).
Run: `git status --short app/` → nothing.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/t1_map.svg
git commit -m "docs(journeys): T1 technician constraint-flip journey + map" -- docs/UX_JOURNEYS.md docs/journeys/t1_map.svg
```

---

## Task 3: T2 — Supervisor, work done before login

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (insert after T1)
- Create: `docs/journeys/t2_map.svg`

- [ ] **Step 1: Harvest ground truth**

Run: `python -m scripts.pre_shift_run`
Transcribe from the console + the newest `reports/preshift_*.md`:
- `«NURGENT»` ← count of assets needing attention
- `«NCRIT»` ← critical count
- `«ALERTDEST»` ← the role address alerts routed to (expect `shift-supervisor@plant.local` for CRITICAL)
Run it a **second time** and note the dedup behavior (`«DEDUP»` ← the already-alerted wording). Do not commit `reports/` or `data/notifications.jsonl`.

- [ ] **Step 2: Write `docs/journeys/t2_map.svg`**

Reuse the exact SVG scaffold from Task 2 Step 2 (same dimensions, palette, 5 steps at x-centers 160, 380, 600, 820, 1040; highlight = step 1, `#B388FF` style). Title: `T2 · Meera, shift supervisor — the shift that starts itself`. Surface chip: `surface: cron + wallboard`. Step labels (action above / system below):

| # | Above | Below | Highlight |
|---|---|---|---|
| 1 | "05:45 — nobody is logged in. The scan runs itself." | `pre_shift_run` scores all 12 assets | ★ yes — "Systems of Action" |
| 2 | "Alerts are already routed by role" | `alert_dispatch_tool` → supervisor/reliability/maintenance, deduped per day | no |
| 3 | "She reads the briefing: counts, top risks, drafted WOs" | `reports/preshift_*.md` | no |
| 4 | "Glances at the wallboard across the room" | `?wallboard=1` — top cards, auto-refresh | no |
| 5 | "Handover takes minutes, not war stories" | every claim traceable to the report | no |

- [ ] **Step 3: Write the T2 section into `docs/UX_JOURNEYS.md`**

Use the shared template:

- Cold open: *"It's 05:45. No one has logged in — but the plant has already been scanned, scored, and the night's new risk routed to the right inboxes."*
- Journey: 5 numbered steps mirroring the map table above, with `«NURGENT»`,
  `«NCRIT»`, `«ALERTDEST»`, `«DEDUP»` resolved; include
  `![Pre-shift briefing](journeys/t2_preshift.png)` after step 3 and
  `![Wallboard](journeys/t2_wallboard.png)` after step 4.
- What to notice: cron-friendly autonomy (same brain, proactive); role routing
  from `config.py ALERT_ROLES`; dedup discipline (alarm fatigue is a safety
  hazard); zero-LLM cost — the deterministic pipeline did all of it.
- Demo script (1:30): 0:00 run `python -m scripts.pre_shift_run` in a terminal ·
  0:20 open the report file, read counts «NURGENT»/«NCRIT» · 0:45 show
  alert routing line «ALERTDEST» · 1:00 re-run the command, point at dedup ·
  1:10 open `http://localhost:8501/?wallboard=1` · 1:30 end.
- Traceability: 5.4 (alert reports, decision summaries), 6.7 (real-time alerting), 7 (dashboard, role alerts).

- [ ] **Step 4: Verify and commit**

No `«` tokens left in T2. `git status --short app/` → nothing.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/t2_map.svg
git commit -m "docs(journeys): T2 supervisor pre-shift autonomy journey + map" -- docs/UX_JOURNEYS.md docs/journeys/t2_map.svg
```

---

## Task 4: T3 — Reliability engineer, teaching the system

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (insert after T2)
- Create: `docs/journeys/t3_map.svg`

- [ ] **Step 1: Harvest ground truth (this walk mutates runtime files — that's fine, don't commit them)**

Run a Python session:

```python
from agent.orchestrator import run_deterministic
from agent.tools import record_feedback
print(run_deterministic("cooling pump status").answer_markdown)   # before
record_feedback("PUMP-12", note="seal weep recurred on startup",
                correction="actual cause was the mechanical seal, not the bearing",
                severity_adjust=10, outcome="corrected")
print(run_deterministic("cooling pump status").answer_markdown)   # after
```

Transcribe: `«BEFORE_FAULT»` ← Block 2 probable fault in the *before* answer;
confirm the *after* answer's Block 5 shows the continuous-learning line
(`«FBLINE»` ← its wording, e.g. "1 engineer feedback record(s) … (priority
score unaffected)"). Confirm the engineer's own words appear in retrieved
context for PUMP-12 (`rag_tool("seal weep recurred", asset_id="PUMP-12")` →
a `feedback`-type hit).

- [ ] **Step 2: Write `docs/journeys/t3_map.svg`**

Same scaffold, 5 steps; highlight = step 4. Title: `T3 · Dev, reliability engineer — the diagnosis was wrong (and that's the feature)`. Surface chip: `surface: Logbook + Chat`. Labels:

| # | Above | Below | Highlight |
|---|---|---|---|
| 1 | "Reads the Wizard's diagnosis for PUMP-12" | Block 2: «BEFORE_FAULT» | no |
| 2 | "He knows better: it's the seal, not the bearing" | domain expertise the data didn't have | no |
| 3 | "Files the correction + urgency slider" | `record_feedback` → feedback.csv | no |
| 4 | "Asks the same question again" | RAG re-indexed **immediately** — the answer now cites his words | ★ yes |
| 5 | "Score honesty: urgency Δ stored, applied only in calibration mode" | `MW_APPLY_FEEDBACK_BIAS` gate | no |

- [ ] **Step 3: Write the T3 section**

Shared template:

- Cold open: *"The Wizard blamed the bearing on the cooling pump. Dev has rebuilt that pump twice — it's the seal. Thirty seconds later, the system knows it too."*
- Journey: 5 steps per the map; resolve «BEFORE_FAULT», «FBLINE»; include
  `![Re-run cites the engineer](journeys/t3_feedback_cited.png)` after step 4.
- What to notice: the learning loop closes *on camera*; two-channel honesty —
  retrieval learns immediately, the priority score does **not** move unless
  calibration mode is explicitly on (the UI microcopy says so); tacit knowledge
  becomes structured, citable context (this is the seed of the Part-2 F1 vision).
- Demo script (2:00): 0:00 Chat: *cooling pump status*, read Block 2 «BEFORE_FAULT» ·
  0:30 Logbook tab: pick PUMP-12, type the correction, set slider +10, submit ·
  1:10 Chat: same query again · 1:30 point at the feedback citation + Block 5
  «FBLINE» · 2:00 end.
- Traceability: 6.6 (feedback-driven improvement), 4.4 (multi-turn NL), 6.4 (audit trail).

- [ ] **Step 4: Verify and commit**

No `«` tokens in T3. `git status --short app/` → nothing. Runtime files
(`data/feedback.csv`, `knowledge/store/*`) stay uncommitted.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/t3_map.svg
git commit -m "docs(journeys): T3 engineer learning-loop journey + map" -- docs/UX_JOURNEYS.md docs/journeys/t3_map.svg
```

---

## Task 5: T4 — Manager, evidence on demand (+ 🔜 tranche tags)

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (insert after T3)
- Create: `docs/journeys/t4_map.svg`

- [ ] **Step 1: Harvest ground truth**

Run: `streamlit run app/streamlit_app.py` (read-only). From the Plant Bottleneck tab transcribe: `«NASSETS»` (assets monitored), `«NCRIT2»` (critical count), `«NFLAG»` (constraint-flagged count), and the top-ranked asset id `«TOPASSET»`. Stop the server.

- [ ] **Step 2: Write `docs/journeys/t4_map.svg`**

Same scaffold, 5 steps; highlight = step 3. Title: `T4 · Shalini, maintenance manager — "where is tomorrow's downtime coming from?"`. Surface chip: `surface: Bottleneck board`. Labels:

| # | Above | Below | Highlight |
|---|---|---|---|
| 1 | "Monday 08:55 — standup in five minutes" | Plant Bottleneck: «NASSETS» assets ranked | no |
| 2 | "Top of the board: «TOPASSET», ⛔ flagged" | bands from config, never invented by the UI | no |
| 3 | "She clicks one number she doesn't believe" | Deep-Dive evidence room: sensors in σ, SHAP, parts, SQL | ★ yes — evidence in two clicks |
| 4 | "🔜 What does it idle downstream?" | cascade_tool → system priority + topology graph | no (tag 🔜) |
| 5 | "🔜 What if we defer 48h? + KPI row for the standup" | scenario_tool · kpi_summary | no (tag 🔜) |

- [ ] **Step 3: Write the T4 section**

Shared template:

- Cold open: *"Standup is in five minutes and the only honest answer to 'what's our biggest risk?' has to survive being clicked on."*
- Journey: steps 1–3 plain (resolve «NASSETS», «NCRIT2», «NFLAG», «TOPASSET»);
  include `![Bottleneck board](journeys/t4_board.png)` after step 2. Steps 4–5
  carry the **🔜 in-flight** tag with footnote: *"🔜 = approved tranche, plan
  committed (`docs/superpowers/plans/2026-06-12-cascade-scenario-kpi.md`), not
  yet merged. Delete these tags when it lands."*
- What to notice: "AI to build, UI to validate" is the management story —
  numbers that survive interrogation; the board ranking comes from the same
  deterministic tool the evals judge; the 🔜 steps show the roadmap is *planned,
  not vapor* (the plan file is in the repo).
- Demo script (1:30): 0:00 Bottleneck tab, read the counts row «NASSETS»/«NCRIT2»/«NFLAG» ·
  0:20 point at «TOPASSET» card + ⛔ chip · 0:40 Deep-Dive: σ-deviations,
  SHAP bars, parts table · 1:10 mention 🔜 cascade/KPI tranche in one sentence ·
  1:30 end.
- Traceability: 5.2 (risk bands, plant bottleneck), 6.4 (traceability), 7 (dashboard).

- [ ] **Step 4: Verify and commit**

No `«` tokens in T4; 🔜 appears only on steps 4–5. `git status --short app/` → nothing.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/t4_map.svg
git commit -m "docs(journeys): T4 manager evidence journey + in-flight tranche tags" -- docs/UX_JOURNEYS.md docs/journeys/t4_map.svg
```

---

## Task 6: Part 2 — F1 & F2 ROADMAP journeys, storyboards, gap tables

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (Part 2 + Additions sections)
- Create: `docs/journeys/f1_map.svg`, `docs/journeys/f2_map.svg`, `docs/journeys/f1_storyboard.svg`, `docs/journeys/f2_storyboard.svg`, `docs/journeys/today_vs_tobe.svg`

- [ ] **Step 1: Write the two ROADMAP map SVGs (sketch-toned)**

Same scaffold as Task 2 Step 2 but sketch styling so concept ≠ shipped: every `rect` gets `stroke-dasharray="6 3"`, panel fill `#FFFBEB`, stroke `#D97706`, and a top-right badge `<rect … fill="#D97706"/><text fill="#fff">ROADMAP</text>`.

`f1_map.svg` — title `F1 · Shalini — one inbox for the plant (ROADMAP)`, 5 steps, highlight = step 3:

| # | Above | Below |
|---|---|---|
| 1 | "Morning briefing, conversationally: 'what needs me today?'" | plant-scope copilot over orders + risk + KPIs |
| 2 | "Yesterday's IW38 export already ingested" | SAP order list → CSV adapter → work-order table |
| 3 | ★ "'Log a 40-min breakdown on belt 3, bearing noise' — filed, not typed into Excel" | intent router → delays table, asset-linked, cited |
| 4 | "Signs off the day's tasks by name" | identity + signoff gate → daily management board |
| 5 | "breakdowns_final_v7.docx ingested once, searchable forever" | document ingestion → incidents + RAG corpus |

`f2_map.svg` — title `F2 · Arjun — the wrench doesn't stop for paperwork (ROADMAP)`, 5 steps, highlight = step 3:

| # | Above | Below |
|---|---|---|
| 1 | "Coupling lets go mid-shift; he scans the QR on the asset" | deep link → asset deep-dive on the phone |
| 2 | "Reads the SOP checklist, gloves on" | asset-filtered retrieval, 48px targets |
| 3 | ★ "Says what he sees; snaps two photos" | voice note + photo evidence → structured breakdown record |
| 4 | "Ticks isolation steps as he works" | checklist state carries into closure |
| 5 | "End of shift: one signoff, zero retyping" | identity + signoff; logbook entry written for him |

- [ ] **Step 2: Write the two storyboard SVGs**

`f1_storyboard.svg` (1200×360, sketch tone): three side-by-side phone/laptop frames — Frame 1: chat bubble *"log a 40-min breakdown on belt 3, bearing noise"* with reply *"Filed: DLY-#### · CONV-BELT-03 · MECH · 40 min. Linked to open order 4501234? [yes/no]"*; Frame 2: a daily task list with two ticked rows and a "Sign off as Shalini" button; Frame 3: a table row sliding from a Word-doc icon into a database icon labeled *"23 historical breakdowns ingested → searchable"*. Each frame: dashed border `#D97706`, ROADMAP badge.

`f2_storyboard.svg` (1200×360, sketch tone): Frame 1: phone scanning a QR on a gearbox sketch; Frame 2: mic icon + transcribed note + two photo thumbnails attached to GEARBOX-05; Frame 3: checklist 5/5 green with "Shift signoff — Arjun ✓". Same dashed/ROADMAP styling.

`today_vs_tobe.svg` (1200×300): two horizontal lanes labeled **Today** (solid panels, `#F8FAFC`/`#94A3B8`) and **To-be** (dashed, `#FFFBEB`/`#D97706`). Today lane chips: *ranked board · five-block diagnosis · constraint flip · pre-shift autonomy · feedback loop*. To-be lane chips: *IW38 orders in · conversational logging · daily signoff · field capture · legacy docs ingested*. An arrow between lanes labeled *"same brain, wider intake"*.

- [ ] **Step 3: Write F1 + F2 sections and the Additions section**

Both use the shared template **plus** the ROADMAP banner line and end with gap tables (no demo script — instead a line: *"Demo: 30-second storyboard walkthrough of the frames below."*).

F1 cold open: *"Shalini runs the plant from three places that don't talk: IW38 in SAP, the HMI wall, and a Word file called breakdowns_final_v7.docx."*
F1 gap table:

````markdown
| Journey step | Missing today | Feature that closes it | Link | Effort |
|---|---|---|---|---|
| 1 Morning briefing | Plant-scope chat (today's pipeline is per-asset) | Governed manager copilot | FEATURE_RESEARCH §3.5 | M |
| 2 IW38 ingestion | SAP adapter + work-order data contract | **NEW-1** SAP IW38 CSV adapter | NEW | M |
| 3 Conversational logging | Intent router + gated write path beyond feedback | **NEW-3** Conversational intake intent router | NEW | M |
| 4 Daily signoff | User identity; task list; signoff gate | **NEW-4** Identity & signoff · **NEW-5** Daily management board | NEW | M–L |
| 5 Legacy docs | docx/xlsx parsers → incidents/corpus | **NEW-2** Legacy document ingestion | NEW | S–M |
````

F2 cold open: *"A coupling lets go mid-shift. The fix takes forty minutes; today the paperwork takes longer."*
F2 gap table:

````markdown
| Journey step | Missing today | Feature that closes it | Link | Effort |
|---|---|---|---|---|
| 1 QR deep link | `?asset=` query param + printable QR codes | Mobile-lite subset | FEATURE_RESEARCH §3.9 | S |
| 2 Glove-first SOP view | Mobile layout per UIUX spec | Mobile-lite subset | FEATURE_RESEARCH §3.9 | S–M |
| 3 Voice + photo capture | Mic input; `st.camera_input` → logbook attachment | Mobile-lite subset | FEATURE_RESEARCH §3.9 | S |
| 4 Checklist carry | Persist ticked steps into closure | Mobile-lite subset / UIUX §4 | FEATURE_RESEARCH §3.9 | S |
| 5 Shift signoff | User identity; named closure | **NEW-4** Identity & signoff | NEW | M |
````

Additions section (replaces its placeholder comment):

````markdown
# Additions proposed for FEATURE_RESEARCH.md

The F-journeys surface five features the research doesn't yet contain:

1. **NEW-1 · SAP IW38 CSV adapter** — ingest maintenance + calibration order
   exports via the existing CSV-contract seam (ARCHITECTURE_DESIGN §5.2).
2. **NEW-2 · Legacy document ingestion** — Word/Excel breakdown logs →
   incidents table + RAG corpus, one-time migration per asset.
3. **NEW-3 · Conversational intake intent router** — classify a field message
   (breakdown / reading / order reference / closure) and write to the correct
   table through a gated, cited path.
4. **NEW-4 · User identity & signoff** — named closures and a signoff gate
   (today everything is signed "engineer").
5. **NEW-5 · Daily management board** — today's tasks, signoff state, exceptions.
````

- [ ] **Step 4: Verify and commit**

ROADMAP banner present on both F-journeys; every gap-table "Link" either names a real `FEATURE_RESEARCH.md` section (§3.5/§3.9 exist — verify with `Select-String -Path docs/FEATURE_RESEARCH.md -Pattern "3\.5|3\.9"`) or says NEW. `git status --short app/` → nothing.

```bash
git add docs/UX_JOURNEYS.md docs/journeys/f1_map.svg docs/journeys/f2_map.svg docs/journeys/f1_storyboard.svg docs/journeys/f2_storyboard.svg docs/journeys/today_vs_tobe.svg
git commit -m "docs(journeys): F1/F2 roadmap journeys, storyboards, gap tables, research additions" -- docs/UX_JOURNEYS.md docs/journeys/f1_map.svg docs/journeys/f2_map.svg docs/journeys/f1_storyboard.svg docs/journeys/f2_storyboard.svg docs/journeys/today_vs_tobe.svg
```

---

## Task 7: Verification walk + screenshot capture (app runs READ-ONLY)

**Files:**
- Create: 6 PNGs in `docs/journeys/` (names below)
- Modify: `docs/UX_JOURNEYS.md` (only if a script line mismatches the live UI — fix the script, never the app)

- [ ] **Step 1: Start the app**

Run: `streamlit run app/streamlit_app.py` (background). Browser window **1440×900**, default theme. Use the local browser tooling (Playwright MCP / Claude-in-Chrome) or manual capture — either is fine; filenames and content are what matter.

- [ ] **Step 2: Walk T1's demo script line by line with a stopwatch**

Perform each row of T1's script. Capture:
- `docs/journeys/t1_fiveblock_constraint.png` — the five-block answer with Block 1 visible and the constraint wording in view
- `docs/journeys/t1_trace.png` — the expanded trace with the SQL code block visible

If any "Expect on screen" cell is wrong (UI has evolved), correct the script cell in `docs/UX_JOURNEYS.md`. If total time exceeds 2:30, trim narration notes, not steps.

- [ ] **Step 3: Walk T2**

Run `python -m scripts.pre_shift_run` in a terminal; capture
`docs/journeys/t2_preshift.png` (the report markdown open, counts visible) and
`docs/journeys/t2_wallboard.png` (`http://localhost:8501/?wallboard=1`, cards
readable). Fix script cells if mismatched.

- [ ] **Step 4: Walk T3**

Perform the feedback correction flow from T3's script; capture
`docs/journeys/t3_feedback_cited.png` — the re-run answer with the feedback
citation or Block 5 learning line visible. (This mutates `data/feedback.csv` +
`knowledge/store/` — runtime files, do not commit.)

- [ ] **Step 5: Walk T4**

Capture `docs/journeys/t4_board.png` — Plant Bottleneck with the counts row and
the top card's ⛔ chip visible. Stop the app.

- [ ] **Step 6: Verify and commit**

All 6 PNGs exist and render in Markdown preview; no image link in
`docs/UX_JOURNEYS.md` 404s. Run: `git status --short app/` → **nothing** (the
walk was read-only).

```bash
git add docs/journeys/t1_fiveblock_constraint.png docs/journeys/t1_trace.png docs/journeys/t2_preshift.png docs/journeys/t2_wallboard.png docs/journeys/t3_feedback_cited.png docs/journeys/t4_board.png docs/UX_JOURNEYS.md
git commit -m "docs(journeys): verification-walk screenshots; scripts corrected to live UI" -- docs/journeys/t1_fiveblock_constraint.png docs/journeys/t1_trace.png docs/journeys/t2_preshift.png docs/journeys/t2_wallboard.png docs/journeys/t3_feedback_cited.png docs/journeys/t4_board.png docs/UX_JOURNEYS.md
```

---

## Task 8: Deck hooks + final audit

**Files:**
- Modify: `docs/UX_JOURNEYS.md` (Deck hooks section)

- [ ] **Step 1: Fill the Deck hooks section**

````markdown
# Deck hooks

Slide candidates, in pitch order (slide edits in `docs/deck/build_deck.js` are
a separate task):

1. **The flip** — `t1_map.svg` + `t1_fiveblock_constraint.png` (constraint-aware
   reasoning is the signature moment).
2. **Before anyone logs in** — T2's cold open + `t2_wallboard.png` (Systems of
   Action).
3. **Same brain, wider intake** — `today_vs_tobe.svg` (the vision slide).
4. **The cast** — `cast.svg` (who it's for).
````

- [ ] **Step 2: Final audit (spec §9 definition of done)**

- Tag audit: `Select-String -Path docs/UX_JOURNEYS.md -Pattern "🔜"` → hits only
  in T4 steps 4–5 + the legend; `ROADMAP` only in Part 2 + legend.
- Token audit: `Select-String -Path docs/UX_JOURNEYS.md -Pattern "«"` → no hits.
- Traceability: every T-journey's PDF numbers exist in
  `docs/ARCHITECTURE_DESIGN.md` §2's table.
- Links: every relative link/image in the doc resolves; README link works.
- Constraint: `git log --stat -8 -- app/` shows none of this plan's commits
  touched `app/`.
- Evals untouched by this work: `python -m evals.judges` → same result as
  before this plan started.

- [ ] **Step 3: Commit**

```bash
git add docs/UX_JOURNEYS.md
git commit -m "docs(journeys): deck hooks + final audit (UX journeys complete)" -- docs/UX_JOURNEYS.md
```

---

## Out of scope (deliberate YAGNI)

- Any change under `app/` (hard constraint — frontend upgrade in flight).
- Editing `FEATURE_RESEARCH.md` itself (the doc *proposes* additions; merging
  them is a follow-up decision).
- Deck slide implementation in `docs/deck/build_deck.js`.
- Building any F-journey feature.
- Light-theme screenshots, localization, Mermaid alternatives.
