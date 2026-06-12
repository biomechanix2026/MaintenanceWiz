# Cascade Graph + Scenario Tool + KPI Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first tranche of `docs/FEATURE_RESEARCH.md` — the approved plant-cascade/blast-radius graph (`docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`), a what-if `scenario_tool`, and a SQL-evidenced plant-KPI panel — all additive and eval-safe.

**Architecture:** Three independently shippable features sharing one new test suite (`evals/feature_tests.py`, repo `Suite` pattern — **not pytest**). Cascade: pure-stdlib graph core (`agent/cascade.py`) + `cascade_tool` producing a *separate* `system_priority` so `risk_score_tool`, `RISK_WEIGHTS`, and all existing judges stay untouched. Scenario: pure composition of existing verified math (RULModel, NOMINAL z-bands, RISK_WEIGHTS) — registered in both registries but **not** added to the deterministic pipeline (on-demand evidence, same precedent as `fault_mode_tool`). KPI: an unregistered helper (`kpi_summary`) over `sql_query_tool` so every number carries its SQL ("AI to build, UI to validate").

**Tech Stack:** Python, numpy/pandas (core), Streamlit (UI), in-memory SQLite via the existing `Database` class. No new dependencies; the topology graph renders via `st.graphviz_chart` with a DOT *string* (client-side render, no python `graphviz` package).

**Prerequisite:** The MW2 port plan (`2026-06-11-mw2-port.md`) tasks 1–5 are committed. This plan does not depend on its remaining tasks 6–8; the only overlap is README wording (handled in Task 8 here).

**Invariants that MUST survive every task** (from `CLAUDE.md`):
1. New tools go in **both** `TOOL_FUNCS` and `TOOL_SCHEMAS` in `agent/orchestrator.py` (`requirement_judges` FR-01 enforces set-equality).
2. Five-block output contract unchanged — cascade folds into Block 1 + Block 5, no 6th block.
3. `config.py` is the single source of truth — topology spec and tunables live there.
4. `priority_score` / `RISK_WEIGHTS` are never modified — `system_priority` is a separate, additive number (cascade spec decision #2).
5. Never hard-import a production lib at module top level (nothing here needs one; keep it that way).
6. After every task: `python -m evals.judges`, `python -m evals.tool_contract_tests`, `python -m evals.requirement_judges`, `python -m evals.reporting_tests` all green.

**File structure (whole plan):**
- Modify: `config.py` — topology spec (`LINE_FLOW`, `LINE_ASSET_ORDER`, `UTILITY_EDGES`) + `CASCADE_DECAY`, `CASCADE_GAIN`
- Create: `agent/cascade.py` — pure graph core (`build_graph`, `downstream`, `blast_radius`); no import of `agent.tools`
- Modify: `agent/tools.py` — `cascade_tool`, `scenario_tool`, `kpi_summary`
- Modify: `agent/orchestrator.py` — both registries; cascade dispatch in `run_deterministic`; `_render` Block 1 + Block 5; `_structured_from_trace` parity
- Modify: `agent/system_prompt.py` — STEP 4.5 PLANT IMPACT
- Modify: `app/streamlit_app.py` — Tab 1 topology graph + columns + KPI section; Tab 2 downstream panel + scenario workbook
- Modify: `data/generate_mock_data.py` — dump `data/plant_topology.json` (inspect-only)
- Modify: `evals/judges.py` — 2 new cascade cases + judge() extension
- Create: `evals/feature_tests.py` — one Suite covering all three features
- Modify: `README.md` — cascade limitation bullet replaced; tool count

---

## Task 1: Topology config + pure graph core (`agent/cascade.py`)

**Files:**
- Create: `evals/feature_tests.py`
- Modify: `config.py` (append after the feedback-policy section at the end)
- Create: `agent/cascade.py`

- [ ] **Step 1: Write the failing tests**

Create `evals/feature_tests.py`:

```python
"""
Conformance tests for the cascade / scenario / KPI tranche
(docs/superpowers/plans/2026-06-12-cascade-scenario-kpi.md).

Run:  python -m evals.feature_tests
"""
from __future__ import annotations

from evals._harness import Suite, run_suites

suite = Suite("cascade-scenario-kpi")


# ---- C1: graph construction from the config topology ----------------------
@suite.case
def test_C1_graph_edges_from_config():
    from agent.cascade import build_graph
    g = build_graph()
    # intra-line serial (Melt Shop order)
    assert "FURNACE-01" in g["CONV-BELT-08"], "missing serial edge CONV-BELT-08 -> FURNACE-01"
    # consecutive-line bridge (Sinter -> Melt Shop)
    assert "CONV-BELT-08" in g["CONV-BELT-03"], "missing line bridge CONV-BELT-03 -> CONV-BELT-08"
    # utility fan-out
    assert "ROLL-MILL-04" in g["GEARBOX-05"], "missing utility edge GEARBOX-05 -> ROLL-MILL-04"
    assert set(g["PUMP-12"]) == {"FURNACE-01", "HYD-VALVE-07"}, g["PUMP-12"]
    # every node present, leaf has empty adjacency
    assert g.get("ROLL-MILL-11") == [], "leaf must exist with no out-edges"


# ---- C2: BFS downstream + blast radius (spec arithmetic) -------------------
@suite.case
def test_C2_downstream_and_blast_radius():
    from agent.cascade import downstream, blast_radius
    d = downstream("GEARBOX-05")
    assert d == [("ROLL-MILL-04", 1), ("ROLL-MILL-11", 2)], d
    blast, path = blast_radius("GEARBOX-05")
    # 5*0.6^1 + 4*0.6^2 = 4.44 (spec section 7)
    assert abs(blast - 4.44) < 1e-6, blast
    assert [p["asset_id"] for p in path] == ["ROLL-MILL-04", "ROLL-MILL-11"], path
    assert path[0]["criticality"] == 5 and path[0]["hops"] == 1, path[0]
    # leaf asset
    blast0, path0 = blast_radius("ROLL-MILL-11")
    assert blast0 == 0.0 and path0 == [], (blast0, path0)
    # long chain via the line bridges; no duplicates (cycle guard)
    far = downstream("CONV-BELT-03")
    ids = [a for a, _h in far]
    assert ("CONV-BELT-08", 1) in far and ("ROLL-MILL-11", 7) in far, far
    assert len(ids) == len(set(ids)), "duplicate nodes — BFS visited-set broken"
    # unknown asset degrades gracefully
    blast_u, path_u = blast_radius("NO-SUCH-ASSET")
    assert blast_u == 0.0 and path_u == [], "unknown asset must be terminal"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.feature_tests`
Expected: both cases FAIL — `ModuleNotFoundError: No module named 'agent.cascade'`

- [ ] **Step 3: Add the topology spec to `config.py`**

Append at the end of `config.py` (after the `APPLY_FEEDBACK_BIAS` line):

```python
# --------------------------------------------------------------------------
# Plant topology (cascade / bottleneck graph)
# --------------------------------------------------------------------------
# Hybrid spec (see docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md):
# intra-line serial chains + consecutive-line bridges are DERIVED from the two
# structures below; cross-line utility dependencies are AUTHORED explicitly.
# Assets in the registry but absent here are isolated nodes (blast radius 0).
LINE_FLOW = ["Sinter", "Melt Shop", "Caster", "Rolling"]   # material backbone, ordered
LINE_ASSET_ORDER = {            # serial process order within each line
    "Sinter":    ["CONV-BELT-03"],
    "Melt Shop": ["CONV-BELT-08", "FURNACE-01", "LADLE-02"],
    "Caster":    ["PUMP-19", "HYD-VALVE-07"],
    "Rolling":   ["ROLL-MILL-04", "ROLL-MILL-11"],
}
UTILITY_EDGES = {               # explicit cross-line fan-out
    "PUMP-12":       ["FURNACE-01", "HYD-VALVE-07"],   # cooling water
    "COMPRESSOR-09": ["HYD-VALVE-07", "ROLL-MILL-04"], # plant air
    "GEARBOX-05":    ["ROLL-MILL-04"],                 # mechanical drive
    "CRANE-06":      ["FURNACE-01"],                   # charge handling
}
CASCADE_DECAY = 0.6    # per-hop attenuation of downstream weight
CASCADE_GAIN = 3.0     # blast-radius units -> system_priority points
```

- [ ] **Step 4: Create `agent/cascade.py`**

```python
"""
Plant cascade / bottleneck graph - pure graph core.

Builds the asset-interdependency DAG from the config-owned topology spec and
computes each asset's blast radius: the criticality-weighted, hop-decayed mass
of equipment downstream of it. Deliberately does NOT import agent.tools
(cascade_tool there is the only place own-priority and the graph meet), so this
module stays a pure, individually-testable unit.

Spec: docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md
"""
from __future__ import annotations
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def build_graph() -> dict[str, list[str]]:
    """Adjacency map from the config topology. Missing spec -> empty graph
    (feature degrades gracefully: every asset terminal)."""
    g: dict[str, list[str]] = {}

    def add(src: str, dst: str):
        if dst not in g.setdefault(src, []):
            g[src].append(dst)
        g.setdefault(dst, [])

    order_map = getattr(C, "LINE_ASSET_ORDER", {})
    # 1. intra-line serial chains
    for order in order_map.values():
        for a, b in zip(order, order[1:]):
            add(a, b)
    # 2. consecutive-line bridges (last of line k -> first of line k+1)
    flow = getattr(C, "LINE_FLOW", [])
    for k in range(len(flow) - 1):
        src_line = order_map.get(flow[k], [])
        dst_line = order_map.get(flow[k + 1], [])
        if src_line and dst_line:
            add(src_line[-1], dst_line[0])
    # 3. authored cross-line utility edges
    for src, dsts in getattr(C, "UTILITY_EDGES", {}).items():
        for d in dsts:
            add(src, d)
    return g


def downstream(asset_id: str) -> list[tuple[str, int]]:
    """Directed BFS from asset_id: [(downstream_asset, hops)] in BFS order.
    The visited set is a defensive guard - the topology is a DAG by
    construction, but an authored cycle must not hang the agent."""
    g = build_graph()
    seen = {asset_id}
    out: list[tuple[str, int]] = []
    frontier = [(asset_id, 0)]
    while frontier:
        node, hops = frontier.pop(0)
        for nxt in g.get(node, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            out.append((nxt, hops + 1))
            frontier.append((nxt, hops + 1))
    return out


def blast_radius(asset_id: str) -> tuple[float, list[dict]]:
    """Blast = sum over downstream d of criticality(d) * CASCADE_DECAY^hops(d).
    Returns (score, path detail ordered by hops then criticality desc)."""
    reg = pd.read_csv(C.ASSET_REGISTRY_CSV)
    meta = {r["asset_id"]: (r["name"], int(r["criticality"])) for _, r in reg.iterrows()}
    blast = 0.0
    path: list[dict] = []
    for aid, hops in downstream(asset_id):
        name, crit = meta.get(aid, (aid, 0))
        blast += crit * (C.CASCADE_DECAY ** hops)
        path.append({"asset_id": aid, "name": name, "hops": hops, "criticality": crit})
    path.sort(key=lambda d: (d["hops"], -d["criticality"]))
    return round(blast, 4), path


if __name__ == "__main__":
    g = build_graph()
    print(f"{len(g)} nodes, {sum(len(v) for v in g.values())} edges")
    for aid in ("GEARBOX-05", "CONV-BELT-03", "ROLL-MILL-11"):
        b, p = blast_radius(aid)
        print(f"{aid}: blast={b}  downstream={[d['asset_id'] for d in p]}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m evals.feature_tests`
Expected: `✓ C1-GRAPH-EDGES-FROM-CONFIG PASS`, `✓ C2-DOWNSTREAM-AND-BLAST-RADIUS PASS` — `TOTAL: 2 passed, 0 failed`

- [ ] **Step 6: Regression (config change only — nothing reads the new keys yet)**

Run: `python -m evals.judges`
Expected: `RESULT: 4/4 judges passed`

- [ ] **Step 7: Commit**

```bash
git add config.py agent/cascade.py evals/feature_tests.py
git commit -m "feat(cascade): config topology spec + pure graph core (blast radius)"
```

---

## Task 2: `cascade_tool` + dual registration

**Files:**
- Modify: `evals/feature_tests.py`
- Modify: `agent/tools.py` (after `risk_score_tool`, before the TOOL 8 alert section)
- Modify: `agent/orchestrator.py` (both registries)

- [ ] **Step 1: Write the failing tests**

Append to `evals/feature_tests.py` (above the `__main__` block):

```python
# ---- C3: cascade_tool contract ---------------------------------------------
@suite.case
def test_C3_cascade_tool_contract():
    from agent.tools import cascade_tool, risk_score_tool
    out = cascade_tool("GEARBOX-05")
    own = risk_score_tool("GEARBOX-05")["priority_score"]
    assert out["own_priority"] == own, out
    assert out["downstream_count"] == 2 and len(out["downstream"]) == 2, out
    assert out["blast_radius"] == 4.44, out
    assert out["blast_points"] == round(4.44 * 3.0, 1), out
    assert out["system_priority"] == round(min(100.0, own + out["blast_points"]), 1), out
    assert out["path_str"] == "GEARBOX-05 -> ROLL-MILL-04 -> ROLL-MILL-11", out
    # terminal asset: system priority equals own priority
    leaf = cascade_tool("ROLL-MILL-11")
    assert leaf["downstream_count"] == 0, leaf
    assert leaf["system_priority"] == leaf["own_priority"], leaf
    assert leaf["path_str"] == "ROLL-MILL-11", leaf
    # unknown asset -> error dict, no crash
    bad = cascade_tool("NO-SUCH-ASSET")
    assert "error" in bad, bad


# ---- C4: registered in BOTH registries -------------------------------------
@suite.case
def test_C4_cascade_tool_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    assert "cascade_tool" in TOOL_FUNCS, "missing from TOOL_FUNCS"
    assert any(s["name"] == "cascade_tool" for s in TOOL_SCHEMAS), "missing from TOOL_SCHEMAS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.feature_tests`
Expected: C3 FAIL (`ImportError: cannot import name 'cascade_tool'`), C4 FAIL (`missing from TOOL_FUNCS`)

- [ ] **Step 3: Implement `cascade_tool` in `agent/tools.py`**

Insert after the closing of `risk_score_tool` (after its `return` block, before the `TOOL 8: Real-time alert dispatch` banner comment):

```python
# ==========================================================================
# TOOL 7.5: Plant cascade impact (bottleneck prioritization at plant level)
# ==========================================================================
def cascade_tool(asset_id: str) -> dict:
    """Plant-level impact of this asset failing: which downstream assets idle,
    the criticality-weighted blast radius, and a system_priority that escalates
    own priority by cascade impact. Additive by design - priority_score and
    RISK_WEIGHTS are untouched (eval-baseline safe).
    """
    from agent import cascade
    own_res = risk_score_tool(asset_id)
    if "error" in own_res:
        return {"asset_id": asset_id, "error": own_res["error"]}
    own = own_res["priority_score"]
    blast, path = cascade.blast_radius(asset_id)
    blast_points = round(C.CASCADE_GAIN * blast, 1)
    system_priority = round(min(100.0, own + blast_points), 1)
    return {
        "asset_id": asset_id,
        "own_priority": own,
        "blast_radius": round(blast, 2),
        "blast_points": blast_points,
        "system_priority": system_priority,
        "downstream": path,                      # [{asset_id, name, hops, criticality}]
        "downstream_count": len(path),
        "path_str": " -> ".join([asset_id] + [d["asset_id"] for d in path]),
    }
```

Note: `cascade_tool("NO-SUCH-ASSET")` returns the error dict because `risk_score_tool` returns `{"error": ...}` for unknown assets — that's the graceful-degradation path C3 asserts.

- [ ] **Step 4: Register in BOTH registries** (`agent/orchestrator.py`)

In `TOOL_FUNCS`, after the `"risk_score_tool"` entry:

```python
    "cascade_tool": lambda a: T.cascade_tool(a["asset_id"]),
```

In `TOOL_SCHEMAS`, after the `risk_score_tool` schema dict:

```python
    {"name": "cascade_tool",
     "description": "Plant-level cascade impact for an asset: downstream assets idled by its failure, blast radius, and system_priority (own priority escalated by downstream criticality). Call after risk_score_tool to express plant bottleneck impact.",
     "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
```

- [ ] **Step 5: Run tests + regression**

Run: `python -m evals.feature_tests` — expected: 4 passed.
Run: `python -m evals.requirement_judges` — expected: green (FR-01 set-equality covers the new tool).
Run: `python -m evals.judges` — expected: 4/4 (pipeline untouched so far).

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py agent/orchestrator.py evals/feature_tests.py
git commit -m "feat(agent): cascade_tool - blast radius + system_priority (dual-registered)"
```

---

## Task 3: Deterministic pipeline + renderer + system prompt + judges

**Files:**
- Modify: `agent/orchestrator.py` (`run_deterministic`, `_render`, `_structured_from_trace`)
- Modify: `agent/system_prompt.py`
- Modify: `evals/judges.py`

- [ ] **Step 1: Write the failing judge cases**

In `evals/judges.py`, append two cases to the `CASES` list (after the `abbreviation-eaf` case):

```python
    {
        "name": "gearbox-cascade-impact",
        "query": "what's wrong with the mill gearbox?",
        "expect_asset": "GEARBOX-05",
        "expect_band_in": {"CRITICAL", "HIGH"},
        "expect_constraint_flag": True,
        "expect_tool_called": "cascade_tool",
        "expect_downstream_min": 1,          # GEARBOX-05 idles the rolling mills
    },
    {
        "name": "leaf-asset-terminal",
        "query": "status of the cold roll stand",
        "expect_asset": "ROLL-MILL-11",
        "expect_band_in": {"LOW", "MEDIUM"},
        "expect_constraint_flag": False,
        "expect_tool_called": "cascade_tool",
        "expect_terminal": True,             # last asset in the flow: no dependents
    },
```

In `judge()`, after the `abnormality = res.structured.get("abnormality", {})` line add:

```python
    cascade = res.structured.get("cascade", {})
```

and after the `expect_catastrophic_risk` block add:

```python
    if "expect_downstream_min" in case:
        checks["downstream_count"] = (
            cascade.get("downstream_count", -1) >= case["expect_downstream_min"])
        checks["system_priority_escalated"] = (
            cascade.get("system_priority", -1) >= risk.get("priority_score", 101))
    if case.get("expect_terminal"):
        checks["terminal_no_downstream"] = cascade.get("downstream_count", -1) == 0
        checks["system_equals_own"] = (
            cascade.get("system_priority") == risk.get("priority_score"))
```

- [ ] **Step 2: Run judges to verify the new cases fail**

Run: `python -m evals.judges`
Expected: `RESULT: 4/6 judges passed` — the two new cases fail on `tool_called` / `downstream_count` (cascade_tool not yet dispatched by the pipeline).

- [ ] **Step 3: Dispatch + render in `agent/orchestrator.py`**

3a. In `run_deterministic`, after the `risk = _dispatch("risk_score_tool", ...)` line and before the `sql = _dispatch(...)` line, add:

```python
    casc = _dispatch("cascade_tool", {"asset_id": aid}, trace)
```

3b. In the same function, extend `res.structured` (the dict currently holding `asset_id`, `risk`, `prognostic`, …) with one entry:

```python
                      "cascade": casc,
```

(placed after `"risk": risk,`)

3c. Change the `_render` call at the end of `run_deterministic` to pass it:

```python
    res.answer_markdown = _render(query, aid, prog, shap, top, abnormality, risk, delays,
                                  inv, sops, incidents, probable, sql, alert_line, casc)
```

3d. Change the `_render` signature:

```python
def _render(query, aid, prog, shap, top, abnormality, risk, delays, inv, sops, incidents,
            probable, sql, alert_line, casc):
```

3e. Inside `_render`, before the `md = f"""### 1. ...` assignment, build the two new fragments:

```python
    if casc.get("downstream_count"):
        system_line = (f"\n- **System impact:** idles **{casc['downstream_count']}** downstream asset(s) → "
                       f"system priority **{casc['system_priority']}/100** "
                       f"(blast radius {casc['blast_radius']})")
        casc_md = f"\n- **Cascade path:** `{casc['path_str']}`"
    else:
        system_line = "\n- **System impact:** terminal asset — no downstream dependents"
        casc_md = ""
```

3f. In the `md` f-string, Block 1's delay-severity line currently ends with `{alert_line}`. Append `{system_line}` directly after it:

```python
- **Delay severity:** {delays['events']} events, {delays['total_downtime_min']} min downtime, {delays['tonnage_lost']:.0f} t lost{alert_line}{system_line}
```

3g. In Block 5, the SQL code fence currently closes with ` ```{fb_md}`. Insert `{casc_md}` before `{fb_md}`:

```python
```{casc_md}{fb_md}
```

3h. In `_structured_from_trace` (LLM-mode parity), add to the `out` dict after `"risk": risk,`:

```python
           "cascade": last("cascade_tool"),
```

- [ ] **Step 4: Add STEP 4.5 to `agent/system_prompt.py`**

Between the STEP 4 and STEP 5 lines in `SYSTEM_PROMPT`, insert:

```
STEP 4.5 PLANT IMPACT: call cascade_tool for the resolved asset; fold the
        downstream system impact into Block 1 and the cascade path into Block 5.
```

- [ ] **Step 5: Run judges + the FULL battery**

Run: `python -m evals.judges`
Expected: `RESULT: 6/6 judges passed`

Run: `python -m evals.feature_tests && python -m evals.tool_contract_tests && python -m evals.requirement_judges && python -m evals.reporting_tests`
Expected: all green. `reporting_tests` `EO05`/`DL01` re-run the judges and parse blocks by `### 4.`/`### 5.` markers — the Block 1/Block 5 additions don't move those markers. If `OUT15` fails, the pre-shift report embedded a changed line — read the assertion, it only checks substrings (`Action queue`, `RUL`, `Drafted WO`, `GEARBOX-05`) which are unaffected.

Smoke: `python -m agent.orchestrator`
Expected: both demo queries print five blocks; the gearbox answer contains "System impact:" and "Cascade path:".

- [ ] **Step 6: Commit**

```bash
git add agent/orchestrator.py agent/system_prompt.py evals/judges.py
git commit -m "feat(agent): cascade in deterministic pipeline, five-block render + judges (6 cases)"
```

---

## Task 4: Dashboard cascade surfaces + topology artifact + README

**Files:**
- Modify: `app/streamlit_app.py` (Tab 1 + Tab 2)
- Modify: `data/generate_mock_data.py`
- Modify: `README.md`

No unit test — UI code; verified by smoke run + the topology artifact check below. (The repo has no UI test layer; logic stays in the already-tested tools.)

- [ ] **Step 1: Extend `plant_scan()` and imports in `app/streamlit_app.py`**

1a. Add `cascade_tool` to the `from agent.tools import (...)` list (after `risk_score_tool,`).

1b. In `plant_scan()`, after the `abn = abnormality_tool(...)` line add `casc = cascade_tool(a["asset_id"])`, and add two keys to the appended row dict (after `"band": ...`):

```python
            "system_priority": casc["system_priority"],
            "downstream_n": casc["downstream_count"],
```

(Sort stays on `priority_score` — the spec keeps the existing ranking; `system_priority` is shown alongside. `cascade_tool` re-calls `risk_score_tool` internally — acceptable at 12 assets.)

1c. In Tab 1's `st.dataframe(df.rename(...))` call, add to the rename map:

```python
                           "system_priority": "System Priority", "downstream_n": "Downstream",
```

- [ ] **Step 2: Topology graph in Tab 1**

2a. Add a module-level helper after `band_badge()`:

```python
def _topology_dot(df: pd.DataFrame) -> str:
    """DOT string for st.graphviz_chart (client-side render - no python
    graphviz dependency). Nodes colored by priority band."""
    from agent.cascade import build_graph
    g = build_graph()
    band = dict(zip(df.asset_id, df.band))
    out = ["digraph plant {", "  rankdir=LR;",
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontcolor="white"];']
    for aid in sorted(g):
        out.append(f'  "{aid}" [fillcolor="{BAND_COLOR.get(band.get(aid, "LOW"), "#27ae60")}"];')
    for src in sorted(g):
        for dst in g[src]:
            out.append(f'  "{src}" -> "{dst}";')
    out.append("}")
    return "\n".join(out)
```

2b. In Tab 1, after the existing `st.caption("⚠️ = part lead time ...")` line, add:

```python
    st.markdown("**Plant topology — failure cascade flow** (node color = priority band; "
                "an upstream failure idles everything downstream of it)")
    try:
        st.graphviz_chart(_topology_dot(df), use_container_width=True)
    except Exception:
        st.caption("Topology graph unavailable — see data/plant_topology.json for the edge list.")
```

- [ ] **Step 3: Downstream blast-radius panel in Tab 2**

In Tab 2's `with right:` column, after the "Independent abnormality evidence" dataframe and before the Workbook expander, add:

```python
        casc = cascade_tool(aid)
        st.markdown("**Downstream blast radius**")
        if casc["downstream_count"]:
            st.caption(f"System priority **{casc['system_priority']}/100** "
                       f"(own {casc['own_priority']} + cascade {casc['blast_points']}); "
                       f"failure idles {casc['downstream_count']} downstream asset(s).")
            st.dataframe(pd.DataFrame(casc["downstream"]), hide_index=True,
                         use_container_width=True)
        else:
            st.caption("Terminal asset — no downstream dependents.")
```

- [ ] **Step 4: Dump `data/plant_topology.json` from the generator**

In `data/generate_mock_data.py` `main()`, after the manuals loop (step 7) and before the final `print("Mock data generated:")`, add:

```python
    # 8. Plant topology (inspection-only artifact; logic always reads config.py)
    from agent.cascade import build_graph
    g = build_graph()
    topo = {
        "nodes": [{"asset_id": aid, "name": name, "type": typ, "line": line,
                   "criticality": crit} for aid, name, typ, line, crit in ASSETS],
        "edges": [{"src": s, "dst": d} for s in sorted(g) for d in g[s]],
    }
    with open(os.path.join(HERE, "plant_topology.json"), "w") as f:
        json.dump(topo, f, indent=2)
```

- [ ] **Step 5: Regenerate data and verify nothing else changed**

Run: `python data/generate_mock_data.py`
Expected: same file list printed + `plant_topology.json` written. The generator is fully deterministic (`random.seed(42)`, fixed `now = datetime(2026, 6, 6, ...)`, and the topology dump makes no `random` calls), so:

Run: `git status --short data/`
Expected: only `?? data/plant_topology.json` (or `A`) — every regenerated CSV/manual is byte-identical. If any CSV shows as modified, STOP and investigate (a `random` call was added before existing draws).

- [ ] **Step 6: Update README**

In `README.md` Limitations, replace the bullet:

```markdown
- **The plant cascade / bottleneck graph is designed but not implemented**
  (see `docs/superpowers/specs/`); plant-level reasoning today is per-asset
  ranking plus the pre-shift action queue.
```

with:

```markdown
- **Plant cascade reasoning is additive.** `cascade_tool` computes blast radius
  and `system_priority` on top of (never inside) the eval-judged
  `priority_score`; the topology spec lives in `config.py`
  (design: `docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md`).
```

- [ ] **Step 7: Smoke-run the dashboard + full battery**

Run: `streamlit run app/streamlit_app.py` — verify: Tab 1 shows the topology graph + System Priority / Downstream columns; Tab 2 (GEARBOX-05) shows the two-row downstream table; Tab 2 (ROLL-MILL-11) shows "Terminal asset". Stop the server.

Run: `python -m evals.judges && python -m evals.feature_tests && python -m evals.tool_contract_tests && python -m evals.requirement_judges && python -m evals.reporting_tests`
Expected: all green (`DL03`/`DL02` re-read README — the edited bullet keeps the word "limitation" section intact).

- [ ] **Step 8: Commit**

```bash
git add app/streamlit_app.py data/generate_mock_data.py data/plant_topology.json README.md
git commit -m "feat(ui): plant topology graph, system-priority columns, downstream panel (cascade complete)"
```

---

## Task 5: `scenario_tool` — what-if simulation core

**Files:**
- Modify: `evals/feature_tests.py`
- Modify: `agent/tools.py` (after `cascade_tool`)
- Modify: `agent/orchestrator.py` (both registries)

Design: pure composition of existing verified math. NOT added to the deterministic pipeline — it is on-demand evidence (chat what-ifs, Workbook UI), the same precedent as `fault_mode_tool`. No system-prompt change: the tool description drives LLM usage, consistent with that precedent.

- [ ] **Step 1: Write the failing tests**

Append to `evals/feature_tests.py`:

```python
# ---- S1: no-op scenario reproduces the baseline -----------------------------
@suite.case
def test_S1_scenario_noop_matches_baseline():
    from agent.tools import scenario_tool
    out = scenario_tool("GEARBOX-05")
    assert out["projected"]["rul_days"] == out["baseline"]["rul_days"], out
    # rounding tolerance: risk components are 2dp-rounded in the baseline output
    assert abs(out["delta"]["priority_score"]) <= 0.5, out
    assert out["scenario"] == {"sensor_overrides": {}, "delay_days": 0.0}, out


# ---- S2: deferring intervention raises urgency + re-fires the constraint ----
@suite.case
def test_S2_scenario_defer_raises_priority():
    from agent.tools import scenario_tool
    out = scenario_tool("GEARBOX-05", delay_days=60)
    p, b = out["projected"], out["baseline"]
    assert p["effective_rul_days"] <= p["rul_days"], out
    assert p["priority_score"] >= b["priority_score"], out
    # PINION-G5 (45d lead, qty 0) cannot arrive within the deferred window
    assert p["constraint_flag"], "constraint must fire when deferral burns the RUL margin"


# ---- S3: sensor overrides flow through model + z-bands ----------------------
@suite.case
def test_S3_scenario_override_degrades_healthy_asset():
    from agent.tools import scenario_tool, prognostic_tool
    base = prognostic_tool("CRANE-06")["latest_readings"]
    out = scenario_tool("CRANE-06", sensor_overrides={"vibration": base["vibration"] * 2})
    assert out["projected"]["abnormality_status"] in {"WARNING", "CRITICAL"}, out
    assert out["projected"]["rul_days"] <= out["baseline"]["rul_days"], out
    assert out["scenario"]["sensor_overrides"] == {"vibration": base["vibration"] * 2}, out
    # unknown asset degrades to an error dict
    assert "error" in scenario_tool("NO-SUCH-ASSET"), "unknown asset must not crash"


# ---- S4: registered in BOTH registries --------------------------------------
@suite.case
def test_S4_scenario_tool_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    assert "scenario_tool" in TOOL_FUNCS, "missing from TOOL_FUNCS"
    assert any(s["name"] == "scenario_tool" for s in TOOL_SCHEMAS), "missing from TOOL_SCHEMAS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m evals.feature_tests`
Expected: S1–S3 FAIL (`ImportError: cannot import name 'scenario_tool'`), S4 FAIL (`missing from TOOL_FUNCS`)

- [ ] **Step 3: Implement `scenario_tool` in `agent/tools.py`**

Insert directly after `cascade_tool`:

```python
# ==========================================================================
# TOOL 7.6: What-if scenario simulation (on-demand evidence; not in the
# deterministic pipeline - same precedent as fault_mode_tool)
# ==========================================================================
def scenario_tool(asset_id: str, sensor_overrides: dict | None = None,
                  delay_days: float = 0.0) -> dict:
    """Project RUL, failure probability, priority band, abnormality status and
    the spares constraint under hypothetical sensor readings and/or a deferred
    intervention. Pure recomputation through the SAME verified components
    (RULModel, NOMINAL z-bands, RISK_WEIGHTS) - no new model, nothing invented.
    """
    base_prog = prognostic_tool(asset_id)
    if "error" in base_prog:
        return {"asset_id": asset_id, "error": base_prog["error"]}
    base_risk = risk_score_tool(asset_id)
    atype = base_prog["asset_type"]

    overrides = {k: float(v) for k, v in (sensor_overrides or {}).items()
                 if k in SENSOR_FEATURES}
    readings = dict(base_prog["latest_readings"])
    readings.update(overrides)

    m = _model()
    rul = round(m.predict_rul(atype, readings), 1)   # same rounding risk_score_tool sees
    prob = m.failure_probability(atype, readings)
    effective_rul = max(0.0, rul - float(delay_days))

    # abnormality status from the config z-bands (point-in-time; no trend -
    # a hypothetical reading has no history)
    devs = _deviations(atype, readings)
    max_abs = max((abs(z) for z in devs.values()), default=0.0)
    if max_abs >= C.ANOMALY_CRITICAL_Z:
        abn_status = "CRITICAL"
    elif max_abs >= C.ANOMALY_WARNING_Z:
        abn_status = "WARNING"
    else:
        abn_status = "NORMAL"

    # priority under the scenario: recompute the RUL component against the
    # effective RUL; reuse the other verified components. Any applied feedback
    # bias (priority_score - base_score) carries through unchanged.
    comp = base_risk["components"]
    rul_score = max(0.0, 1 - effective_rul / MAX_RUL_DAYS)
    raw = 100 * (
        RISK_WEIGHTS["rul"] * rul_score +
        RISK_WEIGHTS["criticality"] * comp["criticality_score"] +
        RISK_WEIGHTS["delay_history"] * comp["delay_score"] +
        RISK_WEIGHTS["spares"] * comp["spares_score"]
    )
    bias_applied = base_risk["priority_score"] - base_risk["base_score"]
    score = round(max(0.0, min(100.0, raw + bias_applied)), 1)

    inv = inventory_tool(asset_id)
    out_parts = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
    max_lead = max([p["lead_time_days"] for p in out_parts], default=0)
    parts_gap = bool(out_parts) and max_lead > effective_rul

    return {
        "asset_id": asset_id,
        "scenario": {"sensor_overrides": overrides, "delay_days": float(delay_days)},
        "baseline": {
            "rul_days": base_prog["rul_days"],
            "failure_probability_30d": base_prog["failure_probability_30d"],
            "priority_score": base_risk["priority_score"],
            "priority_band": base_risk["priority_band"],
            "constraint_flag": base_risk.get("constraint_flag"),
        },
        "projected": {
            "rul_days": rul,
            "effective_rul_days": round(effective_rul, 1),
            "failure_probability_30d": round(prob, 3),
            "priority_score": score,
            "priority_band": _band(score),
            "abnormality_status": abn_status,
            "deviations": devs,
            "constraint_flag": (
                "LEAD TIME EXCEEDS RUL - part arrives after predicted failure "
                f"({max_lead}d lead vs {effective_rul:.0f}d effective RUL); "
                "shift to monitored degradation strategy."
                if parts_gap else None),
        },
        "delta": {
            "rul_days": round(rul - base_prog["rul_days"], 1),
            "priority_score": round(score - base_risk["priority_score"], 1),
        },
        "basis": ("Recomputation through existing verified tools (RULModel, "
                  "NOMINAL z-bands, RISK_WEIGHTS); no new model."),
    }
```

- [ ] **Step 4: Register in BOTH registries** (`agent/orchestrator.py`)

In `TOOL_FUNCS`, after the `"cascade_tool"` entry:

```python
    "scenario_tool": lambda a: T.scenario_tool(
        a["asset_id"], a.get("sensor_overrides"), a.get("delay_days", 0.0)),
```

In `TOOL_SCHEMAS`, after the `cascade_tool` schema:

```python
    {"name": "scenario_tool",
     "description": "What-if simulation: project RUL, failure probability, priority band, abnormality status and the spares constraint under hypothetical sensor readings (sensor_overrides, e.g. {\"vibration\": 5.0}) and/or a deferred intervention (delay_days). Use for questions like 'what if we wait 48 hours?' or 'what if vibration rises 20%?'.",
     "input_schema": {"type": "object", "properties": {
         "asset_id": {"type": "string"},
         "sensor_overrides": {"type": "object",
                              "description": "Hypothetical sensor values keyed by feature: temperature, vibration, pressure, humidity, power."},
         "delay_days": {"type": "number",
                        "description": "Days the intervention is deferred; RUL margin is consumed by this amount."}},
      "required": ["asset_id"]}},
```

- [ ] **Step 5: Run tests + full battery**

Run: `python -m evals.feature_tests` — expected: 8 passed.
Run: `python -m evals.judges && python -m evals.tool_contract_tests && python -m evals.requirement_judges && python -m evals.reporting_tests` — expected: all green (deterministic pipeline untouched by this task).

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py agent/orchestrator.py evals/feature_tests.py
git commit -m "feat(agent): scenario_tool - what-if RUL/priority/constraint projection"
```

---

## Task 6: Workbook UI upgrade — sliders drive `scenario_tool`

**Files:**
- Modify: `app/streamlit_app.py` (Tab 2 Workbook expander)

- [ ] **Step 1: Replace the Workbook expander body**

In Tab 2, replace the existing expander:

```python
        with st.expander("🔧 Workbook: adjust sensor inputs and recompute"):
            st.caption("Validate the model by perturbing the live readings.")
            new = {}
            for f, v in prog["latest_readings"].items():
                new[f] = st.slider(f, float(v) * 0.5, float(v) * 1.5, float(v), key=f"sl_{aid}_{f}")
            rul2 = model.predict_rul(arow["type"], new)
            st.metric("Recomputed RUL", f"{rul2:.1f} d", f"{rul2 - prog['rul_days']:+.1f} d")
```

with:

```python
        with st.expander("🔧 Workbook: what-if scenario — perturb readings / defer the job"):
            st.caption("Recomputed through the same verified tools the agent uses "
                       "(RUL model, z-bands, risk weights) — nothing is invented.")
            new = {}
            for f, v in prog["latest_readings"].items():
                new[f] = st.slider(f, float(v) * 0.5, float(v) * 1.5, float(v), key=f"sl_{aid}_{f}")
            delay = st.slider("Defer intervention by (days)", 0, 60, 0, key=f"delay_{aid}")
            sc = T.scenario_tool(aid, new, delay)
            p = sc["projected"]
            s1, s2, s3 = st.columns(3)
            s1.metric("Projected RUL", f"{p['effective_rul_days']:.1f} d",
                      f"{sc['delta']['rul_days']:+.1f} d")
            s2.metric("Projected priority", f"{p['priority_score']}/100 {p['priority_band']}",
                      f"{sc['delta']['priority_score']:+.1f}", delta_color="inverse")
            s3.metric("Abnormality (z-bands)", p["abnormality_status"])
            if p["constraint_flag"]:
                st.warning(p["constraint_flag"])
```

(`T` is already imported as `from agent import tools as T`. The unused `model = load_model()` header line stays — the caption at the top of the page still reports `model.kind`.)

- [ ] **Step 2: Smoke-run**

Run: `streamlit run app/streamlit_app.py` — on Tab 2 pick GEARBOX-05, drag "Defer intervention" to 60: projected priority rises and the constraint warning appears. Pick CRANE-06, drag vibration to max: abnormality flips off NORMAL. Stop the server.

- [ ] **Step 3: Regression + commit**

Run: `python -m evals.feature_tests && python -m evals.judges`
Expected: all green.

```bash
git add app/streamlit_app.py
git commit -m "feat(ui): workbook sliders drive scenario_tool (what-if RUL/priority/constraint)"
```

---

## Task 7: `kpi_summary()` — SQL-evidenced plant KPIs

**Files:**
- Modify: `evals/feature_tests.py`
- Modify: `agent/tools.py` (after `task_closure_tool`, before the logbook helpers)

Design: an **unregistered** helper (like `append_logbook` / `learned_bias`), consumed by the UI. Every metric is computed via `sql_query_tool` so each card/table carries the exact SQL behind it. Not an agent tool yet — that arrives with the plant-scope copilot (separate plan, YAGNI now).

- [ ] **Step 1: Write the failing test**

Append to `evals/feature_tests.py`:

```python
# ---- K1: KPI summary shape + SQL evidence -----------------------------------
@suite.case
def test_K1_kpi_summary_shape_and_evidence():
    from agent.tools import kpi_summary
    k = kpi_summary()
    assert k["cards"] and k["tables"], "empty KPI summary"
    for card in k["cards"]:
        assert card["sql"].strip().lower().startswith("select"), card["name"]
        assert card["value"] is not None, card["name"]
    mttr = next(c for c in k["cards"] if c["name"].startswith("MTTR"))
    assert float(mttr["value"]) > 0, mttr
    mtbf = next(c for c in k["cards"] if c["name"].startswith("MTBF"))
    assert float(mtbf["value"]) > 0, mtbf
    stock = next(t for t in k["tables"] if "Stockout" in t["name"])
    assert any(r["part_no"] == "PINION-G5" for r in stock["rows"]), \
        "known out-of-stock part (PINION-G5) missing from stockout table"
    repeat = next(t for t in k["tables"] if "Repeat" in t["name"])
    for t in k["tables"]:
        assert t["sql"].strip().lower().startswith("select"), t["name"]
    assert isinstance(repeat["rows"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m evals.feature_tests`
Expected: K1 FAIL — `ImportError: cannot import name 'kpi_summary'`

- [ ] **Step 3: Implement `kpi_summary` in `agent/tools.py`**

Insert after `task_closure_tool` (before the `Logbook persistence` banner comment):

```python
# --------------------------------------------------------------------------
# Plant KPI summary (UI helper - intentionally NOT a registered agent tool;
# the plant-scope copilot will expose plant queries in its own plan)
# --------------------------------------------------------------------------
def kpi_summary() -> dict:
    """Manager KPI snapshot computed through sql_query_tool, so every number
    carries the exact SQL behind it ("AI to build, UI to validate"). MTBF/MTTR
    are proxies over the delay log: the demo dataset has no labelled
    repair-duration or PM-plan fields (documented gap in FEATURE_RESEARCH.md).
    """
    cards_spec = [
        ("MTTR proxy (avg downtime per delay event)", "min",
         "SELECT ROUND(AVG(downtime_min), 1) AS v FROM delays"),
        ("MTBF proxy (asset-days per delay event)", "d",
         "SELECT ROUND((julianday(MAX(date)) - julianday(MIN(date))) "
         "* (SELECT COUNT(*) FROM assets) / COUNT(*), 1) AS v FROM delays"),
        ("Total downtime", "min",
         "SELECT SUM(downtime_min) AS v FROM delays"),
        ("Tonnage lost", "t",
         "SELECT ROUND(SUM(tonnage_lost), 1) AS v FROM delays"),
        ("Delay events", "",
         "SELECT COUNT(*) AS v FROM delays"),
        ("Incidents on record", "",
         "SELECT COUNT(*) AS v FROM incidents"),
        ("Out-of-stock part lines", "",
         "SELECT COUNT(*) AS v FROM parts WHERE qty_on_hand = 0"),
    ]
    cards = []
    for name, unit, sql in cards_spec:
        out = sql_query_tool(sql)
        rows = out.get("rows") or []
        val = rows[0].get("v") if rows else None
        cards.append({"name": name, "value": val if val is not None else 0,
                      "unit": unit, "sql": out["sql"]})

    tables_spec = [
        ("Worst assets by downtime",
         "SELECT asset_id, COUNT(*) AS events, SUM(downtime_min) AS downtime_min, "
         "ROUND(SUM(tonnage_lost), 1) AS tonnage_lost FROM delays "
         "GROUP BY asset_id ORDER BY downtime_min DESC LIMIT 5"),
        ("Repeat failure modes (same asset + cause, 2+ occurrences)",
         "SELECT asset_id, delay_desc, COUNT(*) AS recurrences, "
         "SUM(downtime_min) AS downtime_min FROM delays "
         "GROUP BY asset_id, delay_desc HAVING COUNT(*) >= 2 "
         "ORDER BY recurrences DESC, downtime_min DESC LIMIT 8"),
        ("Stockout risk (out-of-stock parts by lead time)",
         "SELECT part_no, asset_id, description, lead_time_days, unit_cost_usd "
         "FROM parts WHERE qty_on_hand = 0 ORDER BY lead_time_days DESC"),
    ]
    tables = []
    for name, sql in tables_spec:
        out = sql_query_tool(sql)
        tables.append({"name": name, "rows": out.get("rows") or [], "sql": out["sql"]})

    return {"cards": cards, "tables": tables,
            "basis": "All KPIs computed via sql_query_tool over the read-only store."}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m evals.feature_tests`
Expected: 9 passed (`✓ K1-KPI-SUMMARY-SHAPE-AND-EVIDENCE PASS`)

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py evals/feature_tests.py
git commit -m "feat(kpi): SQL-evidenced plant KPI summary helper (MTTR/MTBF proxies, stockout risk)"
```

---

## Task 8: KPI panel in Tab 1 + README + final battery

**Files:**
- Modify: `app/streamlit_app.py` (Tab 1, after the topology graph from Task 4)
- Modify: `README.md`

- [ ] **Step 1: Render the KPI section**

At the end of Tab 1 (after the topology-graph block added in Task 4), add:

```python
    st.markdown("---")
    st.subheader("Plant KPIs")
    kpi = T.kpi_summary()
    for i in range(0, len(kpi["cards"]), 4):
        cols = st.columns(4)
        for col, card in zip(cols, kpi["cards"][i:i + 4]):
            unit = f" {card['unit']}" if card["unit"] else ""
            col.metric(card["name"], f"{card['value']}{unit}")
    with st.expander("🧾 SQL behind these numbers (validate in UI)"):
        for card in kpi["cards"]:
            st.code(card["sql"], language="sql")
    for t in kpi["tables"]:
        with st.expander(t["name"]):
            if t["rows"]:
                st.dataframe(pd.DataFrame(t["rows"]), hide_index=True,
                             use_container_width=True)
            else:
                st.caption("No rows — absence of data is information in maintenance.")
            st.code(t["sql"], language="sql")
    st.caption("MTBF/MTTR are delay-log proxies; PM compliance and wrench time need "
               "PM-plan and labor data not present in the demo dataset.")
```

- [ ] **Step 2: Update README tool count**

Find the tool-count phrase in `README.md` (reads "the 11-tool suite" or "the 12-tool suite" depending on whether MW2-port Task 8 has landed) and set it to **"the 14-tool suite"** (12 after the MW2 port + `cascade_tool` + `scenario_tool`). If the MW2-port README task has not landed yet, still write 14 — it reflects the registries after this plan.

- [ ] **Step 3: Smoke-run the dashboard**

Run: `streamlit run app/streamlit_app.py` — Tab 1 now shows: metrics row, bar chart, triage table with System Priority / Downstream, topology graph, then the Plant KPIs section with 7 metric cards and 3 evidence expanders, each ending in its SQL. Stop the server.

- [ ] **Step 4: Run the FULL battery**

Run: `python -m evals.feature_tests && python -m evals.judges && python -m evals.tool_contract_tests && python -m evals.requirement_judges && python -m evals.reporting_tests`
Expected: every suite green; `feature_tests` = 9 passed; `judges` = 6/6. (`python -m evals.port_tests` may print environment GAPs for optional artifacts — those are documented, not failures.)

- [ ] **Step 5: Commit**

```bash
git add app/streamlit_app.py README.md
git commit -m "feat(ui): plant KPI panel with per-metric SQL evidence (tranche complete)"
```

---

## Out of scope (deliberate YAGNI)

- Folding blast radius into `risk_score_tool` / `RISK_WEIGHTS` — explicitly rejected by the approved spec to keep the eval baseline stable.
- Re-ranking Tab 1 by `system_priority` — additive only; the existing `priority_score` ranking is the judged contract.
- Registering `kpi_summary` as an agent tool and plant-scope chat questions — the governed-copilot plan (FEATURE_RESEARCH.md §3.5) owns that.
- `scenario_tool` in the deterministic pipeline — it is on-demand evidence; the five-block contract doesn't have a scenario block.
- PM compliance / wrench-time KPIs — require new mock-data contracts (PM plans, labor hours); belongs to the planner-board plan (§3.6).
- Probabilistic per-edge cascade propagation — the decay model is sufficient (spec §9).
