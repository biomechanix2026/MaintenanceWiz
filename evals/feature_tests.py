"""
Conformance tests for the cascade / next-shift-planner tranche
(docs/superpowers/plans/2026-06-13-next-shift-planner-mvp.md and
 docs/superpowers/plans/2026-06-12-cascade-system-priority.md).

Run:  python -m evals.feature_tests
"""
from __future__ import annotations

from evals._harness import Suite, run_suites

suite = Suite("cascade-planner")


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
    assert len(ids) == len(set(ids)), "duplicate nodes - BFS visited-set broken"
    # unknown asset degrades gracefully
    blast_u, path_u = blast_radius("NO-SUCH-ASSET")
    assert blast_u == 0.0 and path_u == [], "unknown asset must be terminal"


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


# ---- C4: cascade_tool registered in BOTH registries ------------------------
@suite.case
def test_C4_cascade_tool_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    assert "cascade_tool" in TOOL_FUNCS, "missing from TOOL_FUNCS"
    assert any(s["name"] == "cascade_tool" for s in TOOL_SCHEMAS), "missing from TOOL_SCHEMAS"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
