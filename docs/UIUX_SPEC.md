# Maintenance Wizard — UI/UX Design Specification

> **Audience:** Mechanical maintenance teams in a steel factory — field technicians, reliability engineers, shift supervisors.
> **Companion:** `docs/ARCHITECTURE_DESIGN.md`. The UI renders the harness's `AgentResult` (five-block answer + trace + structured data) and is **mode-agnostic** — identical in LLM and deterministic modes.
> **Design north star:** "AI to build, UI to validate." The interface exists to let a human inspect, trust, and act on agent output — fast, with gloves on, in bad light.

---

## 1. Environment & users (design constraints first)

A steel plant floor is hostile to ordinary UI: high ambient glare near furnaces and deep shadow in pits; dust and grease on screens; users wearing **gloves and safety glasses** (often tinted); ambient noise > 85 dB (no audio cues as sole channel); intermittent Wi-Fi away from access points; shared rugged tablets and control-room wallboards rather than personal devices; time pressure measured in lost tonnage per minute.

### Personas

| Persona | Context | Primary need | Primary surface |
|---|---|---|---|
| **Field technician** ("wrench in hand") | On the floor, gloved, interrupted constantly | What do I fix, in what order, with which steps and parts | Rugged tablet / phone |
| **Reliability engineer** | Desk + floor walks | Why is the score what it is; trends; calibrate the system | Laptop |
| **Shift supervisor** | Control room | Plant-wide bottlenecks, critical alerts, shift handover | Wallboard + laptop |

### Design principles

1. **Glanceable severity** — risk band readable from 3 m on a wallboard, 1 m on a tablet.
2. **Never color alone** — every severity state pairs color + icon + label (color-blind and tinted-glasses safe).
3. **Glove-first** — minimum touch target 48×48 px (56 px for primary actions); no hover-dependent information; no long-press as the only path.
4. **Evidence on demand** — headline first, proof one tap away (trace, SQL, SOP source). Trust is built by inspectability, not assertion.
5. **Degrade loudly, fail never** — the fallback ladder means the app always runs; the UI must *state* which mode it's in, never pretend.
6. **One screen, one decision** — each view answers exactly one question (what's worst? / what's wrong with this one? / what do I do? / did we close it out?).

---

## 2. Information architecture

Five tabs, mapping 1:1 onto the existing app and the agent tool suite:

```
┌──────────────────────────────────────────────────────────────────────┐
│ MAINTENANCE WIZARD        ● mode: LLM | DETERMINISTIC   ⟳ data: 09:41 │
├──────────────────────────────────────────────────────────────────────┤
│ [① Plant Bottleneck] [② Asset Deep-Dive] [③ Wizard Chat]             │
│ [④ Pre-Shift Report] [⑤ Digital Logbook]                             │
└──────────────────────────────────────────────────────────────────────┘
```

A persistent **status strip** (top): execution mode badge, data freshness timestamp, count of undispatched recommended alerts, offline indicator. The mode badge is a contract from design principle 5 — deterministic mode shows `⚙ DETERMINISTIC (offline-capable)` in neutral grey, LLM mode shows `✦ LLM` in accent color; LLM-failure fallback shows an amber `⚙ FELL BACK` badge with the exception class on tap.

Navigation answers the four operational questions in workflow order:

| Question | Tab | Persona |
|---|---|---|
| What's worst right now? | ① Plant Bottleneck | Supervisor, technician at shift start |
| What's wrong with *this* machine? | ② Asset Deep-Dive | Technician, reliability engineer |
| Tell me / ask anything | ③ Wizard Chat | All |
| What does the shift need to know? | ④ Pre-Shift Report | Supervisor |
| Close it out and teach the system | ⑤ Digital Logbook | Technician |

---

## 3. Visual design system

### 3.1 Severity tokens (the core vocabulary)

Bands come from `PRIORITY_BANDS` in `config.py` — the UI never invents its own cutoffs.

| Band | Color | Hex (on dark) | Icon | Label |
|---|---|---|---|---|
| CRITICAL | Red | `#FF4D4F` | ⬛ filled octagon | `CRITICAL` |
| HIGH | Orange | `#FF9F1C` | ▲ triangle | `HIGH` |
| MEDIUM | Yellow | `#FFD60A` | ◆ diamond | `MEDIUM` |
| LOW | Green | `#34C759` | ● circle | `LOW` |
| Abnormality states | — | — | ⚡ | `NORMAL / WARNING / CRITICAL` (z-thresholds from config) |

All severity chips: icon + label + color, ≥ 4.5:1 contrast against background, 7:1 for CRITICAL text. Constraint flag gets its own token: `⛔ PART CANNOT ARRIVE IN TIME` — purple `#B388FF` chip, because it changes the recommendation class and must not be confused with severity.

### 3.2 Theme & typography

- **Dark theme default** (high-glare floors favor dark surfaces with bright type; near-black `#121417`, panels `#1C1F24`). Light theme available for office use.
- Type scale (tablet): KPI numerals 40 px bold tabular; section headers 22 px; body 18 px; captions 15 px minimum — nothing smaller, ever. Wallboard mode scales ×1.8.
- Numerals: tabular lining figures so RUL/score columns align and changes are scannable.
- Font: a high-legibility industrial sans (e.g., Inter / Noto Sans) — open apertures, distinguishable `1/l/I`, `0/O`.

### 3.3 Layout & touch

- 8 px spacing grid; cards over tables on touch surfaces; tables for the engineer's desktop density toggle.
- Touch targets ≥ 48 px, primary CTAs ≥ 56 px, spaced ≥ 8 px apart.
- Destructive/side-effectful actions (dispatch alert, close work order) use two-step confirm — **never** undoable-less single tap (gloves cause mis-taps).

---

## 4. Screen specifications

### ① Plant Bottleneck (the triage wall)

**Question answered:** what's worst right now?
**Data:** `risk_score_tool` + `abnormality_tool` for all 12 assets.

```
┌────────────────────────────────────────────────────────────────┐
│ PLANT BOTTLENECK            scanned 09:41  [⟳ Rescan] [Filter] │
│ ┌──────────────────────────┐ ┌──────────────────────────┐      │
│ │ ⬛ CRITICAL  87/100       │ │ ▲ HIGH  71/100           │      │
│ │ VALVE-09 · Caster line   │ │ GEARBOX-05 · Mill drive  │      │
│ │ RUL 11d  ⚡CRIT  ⛔part   │ │ RUL 24d  ⚡WARN           │      │
│ │ [Open Deep-Dive →]       │ │ [Open Deep-Dive →]       │      │
│ └──────────────────────────┘ └──────────────────────────┘      │
│  … ranked descending, CRITICAL row pinned & full-width …       │
└────────────────────────────────────────────────────────────────┘
```

- Ranked card grid, score descending. CRITICAL cards span full width and sit above the fold.
- Each card: severity chip, asset id + plain name + line, score, RUL, abnormality chip, constraint chip if fired. One tap → Deep-Dive with focus set.
- Filters: band, asset type, line/area. Persisted per device.
- **Wallboard mode** (`?wallboard=1`): top-6 cards, ×1.8 type, auto-refresh 5 min, no interactive chrome — readable across a control room.

### ② Asset Deep-Dive (the evidence room)

**Question answered:** what's wrong with this machine and why should I believe it?
**Data:** `prognostic_tool`, `abnormality_tool`, `risk_score_tool`, `inventory_tool`.

Layout — fixed header + four stacked evidence panels:

1. **Header strip:** asset id, name, type, line; severity chip; score; RUL with trend arrow; failure probability; constraint chip. This strip is the "stand-up summary" — everything a supervisor asks, in one line.
2. **Sensor panel:** five sparkline tiles (temperature, vibration, pressure, humidity, power), each showing current value, deviation in σ vs `NOMINAL` (the number technicians learn to trust), and warning/critical z-bands as shaded zones. Breached tiles get the abnormality chip.
3. **Why panel (SHAP):** horizontal bar chart of ranked drivers labeled in plain language — "Vibration +3.1σ above healthy — main driver of the RUL prediction." Attribution method captioned (TreeSHAP vs ablation) per the transparency principle.
4. **Parts panel:** per part — number, description, **IN STOCK n / OUT OF STOCK** chip, lead time vs RUL comparison bar (lead bar overshooting the RUL bar is the visual form of the constraint flag).
5. **Workbook panel:** retrieved SOP/manual sections and prior incidents (source-labeled, asset-filtered), each expandable in place.

Primary CTA (56 px, bottom-fixed): **"Ask the Wizard about this asset"** → opens chat with `focus_asset` set.

### ③ Wizard Chat (the conversation)

**Question answered:** anything — free text, multi-turn, jargon-tolerant.
**Data:** `run_agent()` full pipeline.

- Input: large single field + mic dictation (gloves vs keyboards); quick-prompt chips ("Why is this CRITICAL?", "Show isolation steps", "Parts status", "What changed since yesterday?").
- **Five-block answer rendering** — the contract becomes the layout. Each block is a card with a fixed icon and collapse state tuned by persona need:

| Block | Icon | Default |
|---|---|---|
| 1 Operational Risk Assessment | 🛑 | Expanded — always visible |
| 2 Diagnostic & Root-Cause | 🔬 | Expanded |
| 3 Actionable Maintenance Blueprint | 🧰 | Expanded — **isolation steps as a tappable checklist** |
| 4 Supply-Chain Logistics | 📦 | Collapsed to one summary line, expandable |
| 5 Traceability & Audit Trail | 🧾 | Collapsed; opens sources + SQL |

- **Isolation steps as interactive checklist:** each numbered SOP step gets a 48 px checkbox the technician ticks on the floor; source SOP cited at top ("from SOP-VALVE-09 §Isolation"). Checked state carries into Logbook closure.
- **Trace expander** ("How I got this — N tool calls"): ordered list of `{tool, input, output}` with per-tool icons; SQL rendered in a copyable code block. This is observability as UX — the single biggest trust feature.
- **Asset-resolution clarification:** when confidence < 0.7 the agent's question renders as tappable candidate chips (`VALVE-09 — Caster spray valve`), not free text re-entry.
- **Focus banner:** "In focus: VALVE-09 ✕" pinned above input; follow-ups ("what about its bearings?") visibly resolve against it. Tap ✕ to clear.
- **Alert recommendation banner:** when score ≥ `ALERT_THRESHOLD`, an amber banner: "Auto-alert recommended → would route to shift-supervisor@…" with a two-step **Dispatch** button. Chat never auto-dispatches — the side-effect gate made visible.

### ④ Pre-Shift Report (the briefing)

**Question answered:** what does the incoming shift need to know?
**Data:** `scripts/pre_shift_run.py` output (`reports/preshift_*.md`).

- Header: shift date/time, assets scanned, counts by band, alerts dispatched (with dedup notes).
- Urgent-asset sections in score order, each a condensed five-block summary with "Open Deep-Dive" link.
- Print/PDF-clean stylesheet — the report is read aloud at shift handover; one page per urgent asset, black-on-white.
- History list of prior reports for trend conversation ("it was 71 yesterday, 87 today").

### ⑤ Digital Logbook (closure + teaching the system)

**Question answered:** did we fix it, and what should the system learn?
**Data:** `task_closure_tool`, `record_feedback`, `append_logbook`.

Two-column (stacked on tablet):

- **Close a work order:** work-order id, asset, compliance checklist rendered from `task_closure_tool` — closure button stays disabled with explicit "2 items missing: torque verification, LOTO removal" messaging until complete. Blocked ≠ broken: the gate explains itself.
- **Teach the Wizard (feedback):** asset picker, free-text note/correction ("actual cause was coupling misalignment, not bearing"), outcome selector (confirmed / corrected / false alarm), and a **severity slider −25…+25** labeled in plain terms ("scored too low ←→ too high"). Microcopy states exactly what happens: "Your note is searchable in the next diagnosis immediately. Score adjustment applies only when calibration mode is enabled." Honest about `MW_APPLY_FEEDBACK_BIAS` — never imply learning that isn't on.
- Recent logbook entries list (asset, action, who, when) — the plant's institutional memory, searchable.

---

## 5. Alerting UX

| Aspect | Specification |
|---|---|
| Routing | Severity → role per `ALERT_ROLES` (CRITICAL → supervisor, HIGH → reliability, else maintenance). The UI shows the resolved recipient *before* dispatch. |
| Dedup | "Already alerted today for VALVE-09/CRITICAL" shown as muted state, not error. |
| Channels | v1: notifications.jsonl rendered in-app + status-strip counter. v2: email/webhook adapters; same UI. |
| Acknowledge | Alert list with per-alert ✓ Acknowledge (who + when stamped) so supervisors see pickup. |
| Noise discipline | Alerts only at/above `ALERT_THRESHOLD`; everything else stays on the bottleneck board. Alarm fatigue is a safety hazard — the threshold lives in config, not in the UI. |

---

## 6. Reliability, observability & degraded states

| State | UI behavior |
|---|---|
| LLM unavailable / no key | Grey `⚙ DETERMINISTIC` badge; full functionality; zero feature loss messaging ("running offline pipeline — all answers reproducible"). |
| LLM call failed mid-query | Answer renders from fallback with amber provenance note (mirrors the orchestrator's fallback banner). |
| Chroma/sklearn/shap absent | Silent auto-fallback per ladder; method captions update (e.g., "attribution: ablation"). |
| Stale data | Freshness timestamp turns amber > 2 h, red > 8 h; cards show "data as of…". Never render stale numbers as current. |
| No asset resolved | Candidate chips, never a dead end. |
| Empty states | Every panel has one ("No prior incidents on record") — absence of data is information in maintenance. |

Observability surfaces: trace expander (per answer), SQL echo (per structured claim), mode badge (per session), attribution-method caption (per prediction), feedback provenance line in block 5 (per learning event). **Every number on screen can be traced to a tool output in two taps.**

---

## 7. Accessibility & field usability checklist

- WCAG 2.1 AA minimum; AAA contrast for CRITICAL indicators.
- Color + icon + text for all states (protanopia/deuteranopia + tinted PPE safe).
- Touch ≥ 48 px; primary ≥ 56 px; no hover-only info; no gesture-only paths.
- Body text ≥ 18 px tablet / ≥ 15 px captions; wallboard ×1.8.
- Full keyboard navigation + visible focus rings (desktop engineer use).
- Mic input for chat; all icons labeled; charts carry text equivalents (σ values printed next to sparklines).
- Works at 200 % zoom without horizontal scroll.
- Tolerates dirty-screen mis-taps: confirms on side effects, generous hit slop, undo where reversible.

---

## 8. Core workflows (streamlined to count taps)

**A. Shift-start triage (technician, ≤ 4 taps to work):**
Bottleneck board → tap top CRITICAL card → Deep-Dive scan (header + parts) → "Ask the Wizard" → isolation checklist on screen. Target: < 60 s from app open to first SOP step.

**B. Reactive troubleshooting ("the caster valve is leaking"):**
Chat → dictate query → (chip-tap if clarification) → five-block answer → tick isolation steps on the floor → block 4 tells whether the seal kit exists → constraint chip may flip the plan to monitored degradation.

**C. Supervisor handover:**
Pre-Shift Report auto-generated before shift → wallboard shows top-6 → dispatched alerts already routed and deduped → acknowledge from alert list.

**D. Close-out + learning:**
Logbook → work order → checklist gate (carries chat-ticked steps) → close → feedback card pre-filled with the asset → note + outcome + severity slider → submit → "searchable in next diagnosis immediately."

---

## 9. Implementation notes (Streamlit v1 → v2)

- v1 ships all five tabs in Streamlit (`app/streamlit_app.py`), mode-agnostic via `AgentResult`. The tokens in §3 map to a Streamlit dark theme config + custom CSS for chips and type scale.
- Wallboard mode: query param + `st.fragment` auto-refresh.
- v2 candidates, in value order: (1) PWA shell for offline SOP/checklist caching on tablets, (2) role-based views keyed to `ALERT_ROLES` identities, (3) alert acknowledge persistence, (4) voice answer-readback for hands-busy moments.
- Any new severity, threshold, or band **must** come from `config.py` — the UI is a renderer of the semantic layer, never a second source of truth (invariant 1).
