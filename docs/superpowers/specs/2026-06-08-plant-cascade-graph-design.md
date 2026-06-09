# Plant Cascade & Bottleneck Graph — Design Spec

**Date:** 2026-06-08
**Status:** Approved (ready for implementation planning)
**Component of:** Maintenance Wizard (Agentic AI Challenge — steel-plant decision-support agent)

## 1. Motivation

Today the agent scores every asset **in isolation** (`risk_score_tool` → `priority_score`).
It cannot express that a single failure idles a chain of downstream equipment. The
problem statement explicitly asks for **"bottleneck prioritization at the plant
level"** (Output 5.2), which the current per-asset scoring does not satisfy.

This feature adds an asset-interdependency graph and computes each asset's
**blast radius** — the criticality-weighted, distance-decayed mass of equipment
downstream of it — and a derived **`system_priority`** that elevates upstream
choke points. Example: `GEARBOX-05` fails → `ROLL-MILL-04` (crit 5) idles →
`ROLL-MILL-11` (crit 4) is starved. Per-asset scoring misses this entirely.

It also **surpasses** the requirement: it turns per-asset triage into plant-wide
reasoning and gives the demo a visual, intuitive payoff.

## 2. Approved decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Topology source | **Hybrid** — auto intra-line serial chain + auto consecutive-line bridges, **plus** explicit cross-line utility edges |
| 2 | Scoring integration | **Additive, eval-safe** — new `cascade_tool` + separate `system_priority`; `risk_score_tool`, `RISK_WEIGHTS`, and existing eval judges **untouched** |
| 3 | Output surfacing | **Within the existing five blocks** (Block 1 + Block 5) + plant-level view; no 6th block |
| 4 | Blast-radius algorithm | **Criticality-weighted reachability + hop decay**: `blast = Σ_d criticality(d)·DECAY^hops(d)` |
| 5 | Topology home | **`config.py`** holds the spec (single source of truth); `plant_topology.json` is an inspect-only generated artifact |
| 6 | `system_priority` | `min(100, own_priority + CASCADE_GAIN · blast)` |

## 3. Invariants honored (non-negotiable)

- **`config.py` is the single source of truth** — topology spec and tunables live there.
- **Dual tool registry** — `cascade_tool` is added to *both* `TOOL_FUNCS` and
  `TOOL_SCHEMAS` in `agent/orchestrator.py`.
- **Five-block output is mandatory** — cascade folds into Block 1 and Block 5;
  no block is added or removed.
- **Deterministic mode is the reproducible eval baseline** — `risk_score_tool`
  and `RISK_WEIGHTS` are not modified, so the 4 existing judges keep passing
  unchanged. `priority_score` is preserved; `system_priority` is a new, separate number.
- **Zero-dependency fallback ladder** — the graph is pure numpy/stdlib (dicts +
  BFS). No new hard dependency at module top level. The dashboard graph degrades
  to a table if Graphviz rendering is unavailable.

## 4. Architecture

### 4.1 Config (`config.py`) — topology spec + tunables
```python
LINE_FLOW = ["Sinter", "Melt Shop", "Caster", "Rolling"]   # material backbone, ordered
LINE_ASSET_ORDER = {            # serial process order within each line (derived edges)
    "Sinter":    ["CONV-BELT-03"],
    "Melt Shop": ["CONV-BELT-08", "FURNACE-01", "LADLE-02"],
    "Caster":    ["PUMP-19", "HYD-VALVE-07"],
    "Rolling":   ["ROLL-MILL-04", "ROLL-MILL-11"],
}
UTILITY_EDGES = {               # explicit cross-line fan-out (authored edges)
    "PUMP-12":       ["FURNACE-01", "HYD-VALVE-07"],   # cooling water
    "COMPRESSOR-09": ["HYD-VALVE-07", "ROLL-MILL-04"], # plant air
    "GEARBOX-05":    ["ROLL-MILL-04"],                 # mechanical drive
    "CRANE-06":      ["FURNACE-01"],                   # charge handling
}
CASCADE_DECAY = 0.6    # per-hop attenuation of downstream weight
CASCADE_GAIN  = 3.0    # blast-radius units → system_priority points
```
Edge construction (the "hybrid"):
1. **Intra-line serial:** for each line, chain `LINE_ASSET_ORDER[line][i] → [i+1]`.
2. **Line bridges:** last serial asset of `LINE_FLOW[k]` → first serial asset of `LINE_FLOW[k+1]`.
3. **Utility edges:** add every `src → dst` in `UTILITY_EDGES`.

Result is a DAG. Assets not present in any list are isolated nodes (blast 0).

### 4.2 New module `agent/cascade.py` — pure graph core
No import of `agent.tools` (prevents a circular dependency; `cascade_tool` is the
only place own-priority and graph meet).

- `build_graph() -> dict[str, list[str]]` — adjacency from the config spec.
- `downstream(asset_id) -> list[tuple[str, int]]` — directed BFS returning
  `(downstream_asset, hops)`, with a visited set guarding against accidental cycles.
- `blast_radius(asset_id) -> tuple[float, list[dict]]` — returns the score
  `Σ criticality(d)·CASCADE_DECAY^hops` (criticality read from the asset registry)
  and the contributing path detail `[{asset_id, name, hops, criticality}]`,
  ordered by hops then criticality.

### 4.3 New tool `cascade_tool(asset_id)` in `agent/tools.py`
Composes the graph core with own-priority:
```
own        = risk_score_tool(asset_id)["priority_score"]
blast, path = cascade.blast_radius(asset_id)
blast_points    = round(CASCADE_GAIN * blast, 1)
system_priority = round(min(100.0, own + blast_points), 1)
return {
    "asset_id": asset_id,
    "own_priority": own,
    "blast_radius": round(blast, 2),
    "blast_points": blast_points,
    "system_priority": system_priority,
    "downstream": path,                       # [{asset_id,name,hops,criticality}]
    "downstream_count": len(path),
    "path_str": "ASSET -> d1 -> d2 ...",       # human/audit-readable
}
```
Registered in **both** `TOOL_FUNCS` and `TOOL_SCHEMAS`.

### 4.4 Orchestrator integration (`agent/orchestrator.py`)
- `run_deterministic`: after the existing `risk` dispatch, `_dispatch("cascade_tool", {"asset_id": aid}, trace)`.
- `_render`:
  - **Block 1** gains one line:
    - downstream non-empty → `System impact: idles <N> downstream asset(s) → system priority <S>/100 (blast radius <B>).`
    - downstream empty → `System impact: terminal asset — no downstream dependents.`
  - **Block 5** gains: `Cascade path: <path_str>.` (omitted when terminal).
  - Block headers `### 1.`…`### 5.` are unchanged; no 6th block.

### 4.5 LLM mode (`agent/system_prompt.py`)
Add one pipeline step:
> STEP 4.5 PLANT IMPACT: call `cascade_tool` for the resolved asset; fold the
> downstream system impact into Block 1 and the cascade path into Block 5.

### 4.6 Dashboard (`app/streamlit_app.py`)
- **Tab 1 (Plant Bottleneck):**
  - `plant_scan()` adds `system_priority` and `downstream_count` columns
    (calls `cascade_tool` per asset). **Existing `priority` ranking is retained**
    (additive); `system_priority` shown alongside.
  - A topology graph via `st.graphviz_chart(dot)` built from a generated DOT
    string — renders client-side, **no python `graphviz` dependency**. Nodes
    colored by priority band; cascade/utility edges styled. Wrapped in
    `try/except` → falls back to the existing table if rendering fails.
- **Tab 2 (Deep-Dive):** a "Downstream blast radius" list for the selected asset
  (the `downstream` detail from `cascade_tool`).

### 4.7 Data generator (`data/generate_mock_data.py`)
Dump `data/plant_topology.json` (edge list + node metadata) built from the config
spec — an **inspect-only** artifact for humans/UI, never read back by logic.

## 5. Data flow

```
config.py (LINE_FLOW, LINE_ASSET_ORDER, UTILITY_EDGES, DECAY, GAIN)
   │
   ├─► cascade.build_graph ─► cascade.downstream ─► cascade.blast_radius
   │                                                      │
   │                              risk_score_tool ─┐      │
   │                                               ▼      ▼
   │                                       tools.cascade_tool ──► {system_priority, downstream, path}
   │                                               │
   │              ┌────────────────────────────────┼────────────────────────────┐
   │              ▼                                 ▼                            ▼
   │   orchestrator._render               Streamlit Tab 1 graph +      Streamlit Tab 2
   │   (Block 1 + Block 5 + trace)        system_priority column       downstream list
   │
   └─► generate_mock_data ─► data/plant_topology.json  (inspection only)
```

## 6. Error handling & edge cases

- **Isolated / unknown asset:** `downstream` empty, `blast_radius` 0,
  `system_priority == own_priority`. Block 1 prints the "terminal asset" line.
- **Accidental cycle:** BFS visited-set prevents infinite loops (topology is a
  DAG by construction; this is defensive).
- **Missing topology spec:** `build_graph` returns an empty graph → feature
  degrades gracefully (every asset terminal; no system-impact escalation).
- **Graphviz unavailable in the browser:** `try/except` around
  `st.graphviz_chart` → table-only fallback.

## 7. Testing & verification

- **Unit (`agent/cascade.py`):**
  - `downstream("GEARBOX-05")` == `{ROLL-MILL-04, ROLL-MILL-11}` (hops 1 and 2).
  - `blast_radius("GEARBOX-05")` ≈ `5·0.6¹ + 4·0.6²` = `4.44` (± rounding).
  - A leaf (e.g. `ROLL-MILL-11`) → empty downstream, blast 0.
- **New eval judge (`evals/judges.py`)** — extends the suite to 5 cases:
  - `GEARBOX-05`: `downstream_count > 0`, `system_priority >= priority_score`,
    `cascade_tool` in trace.
  - a leaf asset: `downstream_count == 0`, `system_priority == priority_score`.
- **Regression:** the 4 existing judges still pass unchanged; deterministic
  output still contains `### 1.`…`### 5.`; `python -m agent.orchestrator` smoke run.
- **Run command:** `PYTHONIOENCODING=utf-8 python -m evals.judges` (the repo's
  console encoding workaround for the existing ✓/✗ print on Windows).

## 8. Files touched

| File | Change |
|------|--------|
| `config.py` | + topology spec (`LINE_FLOW`, `LINE_ASSET_ORDER`, `UTILITY_EDGES`) + `CASCADE_DECAY`, `CASCADE_GAIN` |
| `agent/cascade.py` | **new** — pure graph core (`build_graph`, `downstream`, `blast_radius`) |
| `agent/tools.py` | + `cascade_tool` |
| `agent/orchestrator.py` | + `cascade_tool` in `TOOL_FUNCS` and `TOOL_SCHEMAS`; `_render` Block 1 + Block 5; dispatch in `run_deterministic` |
| `agent/system_prompt.py` | + STEP 4.5 |
| `app/streamlit_app.py` | Tab 1 graph + `system_priority`/`downstream_count` columns; Tab 2 downstream list |
| `data/generate_mock_data.py` | dump `data/plant_topology.json` |
| `evals/judges.py` | + cascade judge case(s) |

## 9. Out of scope (YAGNI)

- Probabilistic per-edge propagation (algorithm C) — deferred; decay model is enough.
- Folding blast radius into `risk_score_tool`/`RISK_WEIGHTS` — explicitly rejected
  to keep the eval baseline stable.
- Scheduling/optimized maintenance plan — a separate surpass item, its own spec.
- Replacing the Tab 1 triage ranking with `system_priority` — additive only for now.
```
