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


# ===========================================================================
# Next-shift planner MVP (pure-input cases -> deterministic, no live scoring)
# ===========================================================================
def _cand(aid, atype, sysp, rul=30, crit=4, band="HIGH", flag=None):
    return {"asset_id": aid, "asset_type": atype, "system_priority": sysp,
            "rul_days": rul, "criticality": crit, "priority_band": band,
            "constraint_flag": flag}


# ---- P1: cascade pays off - upstream system_priority outranks isolated ------
@suite.case
def test_P1_planner_cascade_pays_off():
    from agent.planner import plan_shift
    crew = [{"crew_id": "M1", "skill": "mechanical", "shift_hours": 8}]
    templates = {"gearbox": {"task": "Pinion", "est_hours": 4.0, "required_skill": "mechanical"}}
    # ISO has higher own criticality but the UPstream choke point has higher
    # system_priority via cascade -> it must be scheduled first.
    cands = [_cand("ISO", "gearbox", 80, crit=5), _cand("UP", "gearbox", 90, crit=4)]
    out = plan_shift(cands, crew, templates)
    sched = [s["asset_id"] for s in out["scheduled"]]
    assert sched[0] == "UP", sched
    assert set(sched) == {"UP", "ISO"}, sched


# ---- P2: infeasible part -> monitored degradation / procurement -------------
@suite.case
def test_P2_planner_infeasible_part_to_procurement():
    from agent.planner import plan_shift
    crew = [{"crew_id": "M1", "skill": "mechanical", "shift_hours": 8}]
    templates = {"gearbox": {"task": "Pinion", "est_hours": 4.0, "required_skill": "mechanical"}}
    flag = "LEAD TIME EXCEEDS RUL - part arrives after predicted failure (45d lead vs 12d RUL)."
    out = plan_shift([_cand("G", "gearbox", 95, rul=12, band="CRITICAL", flag=flag)], crew, templates)
    assert [p["asset_id"] for p in out["procurement"]] == ["G"], out
    assert "G" not in [s["asset_id"] for s in out["scheduled"]], out
    assert flag in out["procurement"][0]["reason"], out


# ---- P3: crew-hour limit -> lowest-ranked feasible job deferred with reason --
@suite.case
def test_P3_planner_crew_hour_limit_defers():
    from agent.planner import plan_shift
    crew = [{"crew_id": "M1", "skill": "mechanical", "shift_hours": 8}]
    templates = {"mill": {"task": "Roll change", "est_hours": 5.0, "required_skill": "mechanical"}}
    out = plan_shift([_cand("HI", "mill", 90, crit=5), _cand("LO", "mill", 70, crit=4)], crew, templates)
    assert [s["asset_id"] for s in out["scheduled"]] == ["HI"], out
    assert [d["asset_id"] for d in out["deferred"]] == ["LO"], out
    assert "crew" in out["deferred"][0]["reason"].lower(), out


# ---- P4: shift_plan_tool registered in BOTH registries ----------------------
@suite.case
def test_P4_shift_plan_tool_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    assert "shift_plan_tool" in TOOL_FUNCS, "missing from TOOL_FUNCS"
    assert any(s["name"] == "shift_plan_tool" for s in TOOL_SCHEMAS), "missing from TOOL_SCHEMAS"


# ---- P5: no crew overbooked (aggregate-OK but single-crew-insufficient) ------
@suite.case
def test_P5_planner_no_crew_overbooked():
    from agent.planner import plan_shift
    # two mechanical crews, 3h each: aggregate 6h >= 5h, but no single crew fits
    crew = [{"crew_id": "M1", "skill": "mechanical", "shift_hours": 3},
            {"crew_id": "M2", "skill": "mechanical", "shift_hours": 3}]
    templates = {"mill": {"task": "Roll change", "est_hours": 5.0, "required_skill": "mechanical"}}
    out = plan_shift([_cand("BIG", "mill", 90, crit=5)], crew, templates)
    assert [s["asset_id"] for s in out["scheduled"]] == [], "job too big for any single crew must defer"
    assert [d["asset_id"] for d in out["deferred"]] == ["BIG"], out
    # invariant: no crew is allocated beyond its own shift_hours
    crew2 = [{"crew_id": "M1", "skill": "mechanical", "shift_hours": 8}]
    templates2 = {"gearbox": {"task": "Pinion", "est_hours": 4.0, "required_skill": "mechanical"}}
    cands2 = [_cand(f"A{i}", "gearbox", 90 - i) for i in range(3)]   # 3 x 4h vs 8h crew
    out2 = plan_shift(cands2, crew2, templates2)
    per_crew: dict[str, float] = {}
    for s in out2["scheduled"]:
        per_crew[s["crew_id"]] = per_crew.get(s["crew_id"], 0.0) + s["est_hours"]
    for cid, used in per_crew.items():
        cap = next(c["shift_hours"] for c in crew2 if c["crew_id"] == cid)
        assert used <= cap, (cid, used, cap)
    for cid, info in out2["capacity"]["by_crew"].items():
        assert info["used"] <= info["total"], (cid, info)


# ===========================================================================
# CMMS work-order drafts (system-of-action write-back)
# ===========================================================================
@suite.case
def test_W1_work_orders_only_for_scheduled_jobs():
    from agent.tools import work_order_draft_tool, shift_plan_tool
    plan = shift_plan_tool()
    out = work_order_draft_tool()
    wo_assets = {w["asset_id"] for w in out["work_orders"]}
    sched_assets = {s["asset_id"] for s in plan["scheduled"]}
    assert wo_assets == sched_assets, (wo_assets, sched_assets)
    assert out["count"] == len(plan["scheduled"]), out["count"]
    # no WO for procurement-blocked or deferred jobs
    blocked = ({p["asset_id"] for p in plan["procurement"]}
               | {d["asset_id"] for d in plan["deferred"]})
    assert wo_assets.isdisjoint(blocked), (wo_assets, blocked)
    # GEARBOX-05 is procurement-blocked in the demo data -> never a WO
    assert "GEARBOX-05" not in wo_assets, wo_assets


@suite.case
def test_W2_every_work_order_carries_trace_evidence():
    from agent.tools import work_order_draft_tool
    out = work_order_draft_tool()
    assert out["work_orders"], "expected at least one scheduled WO"
    for w in out["work_orders"]:
        assert w["status"] == "DRAFT", w
        assert w["approval"]["required"] is True and w["approval"]["approved"] is False, w
        assert w["crew_id"] and w["planned_hours"] > 0, w
        ev = w["evidence"]
        assert ev["risk"]["priority_score"] is not None and ev["risk"]["priority_band"], ev
        assert ev["cascade"]["system_priority"] is not None, ev
        assert isinstance(ev["spares"], list), ev
        assert isinstance(ev["sop_citations"], list), ev


@suite.case
def test_W3_persist_writes_one_json_per_wo():
    import os as _os, json as _json, glob as _glob, tempfile, shutil
    from agent.tools import work_order_draft_tool
    d = tempfile.mkdtemp(prefix="mw_wo_")
    try:
        dry = work_order_draft_tool(persist=False, out_dir=d)
        assert dry["persisted"] == [] and _glob.glob(_os.path.join(d, "*.json")) == []
        out = work_order_draft_tool(persist=True, out_dir=d)
        files = _glob.glob(_os.path.join(d, "*.json"))
        assert len(files) == out["count"] > 0, (len(files), out["count"])
        rec = _json.load(open(files[0], encoding="utf-8"))
        assert rec["status"] == "DRAFT" and rec["work_order_id"], rec
        again = work_order_draft_tool(persist=True, out_dir=d)
        files_after_second_run = _glob.glob(_os.path.join(d, "*.json"))
        assert len(files_after_second_run) == out["count"] + again["count"], (
            len(files_after_second_run), out["count"], again["count"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


@suite.case
def test_W4_work_order_draft_tool_in_both_registries():
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    assert "work_order_draft_tool" in TOOL_FUNCS, "missing from TOOL_FUNCS"
    assert any(s["name"] == "work_order_draft_tool" for s in TOOL_SCHEMAS), "missing from TOOL_SCHEMAS"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
