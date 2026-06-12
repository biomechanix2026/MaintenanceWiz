# Maintenance Wizard — User Journeys & Demo Script

> Four plant roles, six journeys. Part 1 is **real today** — every step is a click
> you can perform in the running app (deterministic mode, no API key needed), and
> each journey carries a timed demo script. Part 2 is **ROADMAP** — to-be journeys
> that drive our feature planning; nothing in Part 2 is built.

**How to read the tags:** plain step = runs today · 🔜 = approved tranche in
flight ([the cascade/scenario/KPI plan](superpowers/plans/2026-06-12-cascade-scenario-kpi.md)) · ROADMAP =
Part 2 only, not built.

![The cast](journeys/cast.svg)

| Persona | Surface | Lives in |
|---|---|---|
| **Arjun — Field technician** | Rugged tablet on the floor | Wizard Chat, Deep-Dive, Logbook |
| **Meera — Shift supervisor** | Control-room wallboard + laptop | Pre-Shift Report, wallboard, alerts |
| **Dev — Reliability engineer** | Laptop, desk + floor walks | Deep-Dive, Logbook feedback |
| **Shalini — Maintenance manager** | Laptop, morning standup | Bottleneck board, evidence room |

---

## Part 1 — Today (demo-grade)

### T1 · Arjun, field technician — "The part that can't arrive in time"

> *At shift start the mill drive gearbox is trending toward failure — and the
> replacement pinion is 45 days away.*

![T1 journey map](journeys/t1_map.svg)

#### The journey

1. **Arjun types what he'd say to a colleague** — *Wizard Chat*: "what's wrong
   with the mill gearbox?" `resolve_asset` maps the jargon to **GEARBOX-05**.
2. **The answer arrives as five fixed blocks** — risk (**CRITICAL**, 82.0/100,
   RUL **36.1 days**, failure probability 32%), root cause (top driver
   **vibration**, matched against historical incident records), blueprint,
   logistics, audit trail. Same contract every time, both engine modes.

![Five-block answer with constraint chip](journeys/t1_fiveblock_constraint.png)

3. **He opens "how I got this"** — the trace expander lists all 8 tool
   calls with inputs and outputs, including the exact SQL the agent ran.

![The tool trace](journeys/t1_trace.png)

4. **⛔ The flip** — Block 4 shows the drive pinion `PINION-G5` is **out of
   stock with a 45-day lead** — longer than the 36.1-day RUL. The Wizard
   doesn't say "replace now" anyway; the recommendation flips to **monitored
   degradation**: tightened alarms, interim mitigation, expedited procurement.
5. **He works the isolation steps** — Block 3 lists them from **SOP-GBX-05**,
   cited by name. Torque values and steps come only from tool outputs — never
   from model memory.
6. **He closes the work order** — *Digital Logbook*: the closure button stays
   disabled until the compliance checklist (parts recorded, steps logged,
   isolation cleared, follow-up scheduled, logbook entry) is green.

#### What to notice (judges)

- **Step 2:** the five-block contract is identical in LLM and offline
  deterministic mode — run this demo with no API key.
- **Step 3:** observability as UX — every number traces to a tool output.
- **Step 4:** constraint-aware reasoning, not lookup: lead time vs RUL changes
  the *recommendation class*.
- **Step 6:** chat never writes; closure goes through a gated form. Side
  effects are opt-in by design.

#### Demo script (2:30)

| Clock | Action | Expect on screen |
|---|---|---|
| 0:00 | Open the app; point at the engine-mode badge | "Deterministic (offline)" or "LLM" |
| 0:10 | Chat tab → type *what's wrong with the mill gearbox?* | Five block-cards render |
| 0:30 | Read Block 1 aloud | CRITICAL · 82.0/100 · RUL 36.1d |
| 0:50 | Expand the tool trace | 8 calls; SQL in a code block |
| 1:10 | Point at Block 4 part rows | PINION-G5 OUT, 45d lead |
| 1:25 | Read the flip line in Block 3 | "monitored degradation" |
| 1:45 | Logbook tab → tick checklist items one by one | Button enables only at 5/5 |
| 2:15 | Close & log | Logbook entry appears |

#### Traceability

Demonstrates PDF objectives: 4.3 (manuals/spares), 4.4 (NL queries), 5.1
(diagnosis, root cause, RUL), 5.2 (constraint-based priority), 5.3 (step-by-step
actions, procurement strategy), 5.4 (digital log), 6.4 (explainability).

<!-- T2..T4 inserted by Tasks 3-5 -->

---

## Part 2 — To-be (ROADMAP)

<!-- F1..F2 inserted by Task 6 -->

---

## Additions proposed for FEATURE_RESEARCH.md

<!-- filled by Task 6 -->

## Deck hooks

<!-- filled by Task 8 -->
