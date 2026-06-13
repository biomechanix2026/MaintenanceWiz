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


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
