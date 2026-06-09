"""
Direct tool-contract tests (agent/tools.py) for problem-statement requirements.

Run:  python -m evals.tool_contract_tests
"""
from __future__ import annotations
import os

import pandas as pd

import config as C
from config import SENSOR_FEATURES
from agent import tools as T
from evals._harness import Suite, run_suites, sandbox, gap, approx

suite = Suite("tool-contracts")
REG = pd.read_csv(C.ASSET_REGISTRY_CSV)
ASSET_IDS = list(REG.asset_id)


# ---- FR-02: knowledge integration (asset-filtered RAG) --------------------
@suite.case
def test_FR02_rag_integration():
    res = T.rag_tool("bearing seizure vibration root cause", asset_id="CONV-BELT-03", k=6)["results"]
    assert res, "no RAG results"
    assert all(h["asset_id"] == "CONV-BELT-03" for h in res), "cross-asset bleed"
    types = {h["type"] for h in res}
    assert "manual" in types, f"no manual/SOP chunk: {types}"
    assert types & {"incident", "delay_log"}, f"no historical record: {types}"


# ---- FR-05 / IN-05 / IN-07: prognostics + abnormality contract -----------
@suite.case
def test_FR05_prognostic_and_abnormality_contract():
    catastrophic_seen = False
    for aid in ASSET_IDS:
        prog = T.prognostic_tool(aid)
        assert "rul_days" in prog and isinstance(prog["rul_days"], (int, float)), aid
        approx(prog["failure_probability_30d"], 0.0, 1.0)
        assert set(prog["latest_readings"]) == set(SENSOR_FEATURES), f"{aid} sensor features"
        abn = T.abnormality_tool(aid)
        assert abn["status"] in {"NORMAL", "WARNING", "CRITICAL"}, abn["status"]
        assert abn["early_warning"] == (abn["status"] != "NORMAL"), aid
        if abn["catastrophic_risk"]:
            assert abn["status"] == "CRITICAL" and int(REG[REG.asset_id == aid].iloc[0]["criticality"]) >= 4
            catastrophic_seen = True
        assert list(abn["deviations"]) == SENSOR_FEATURES, "deviation feature order"
    assert catastrophic_seen, "no asset ever triggers catastrophic_risk — detector inert"


# ---- IN-06: abnormality alert payload -------------------------------------
@suite.case
def test_IN06_abnormality_payload():
    abn = T.abnormality_tool("CONV-BELT-03")  # heavily degraded asset
    for key in ("status", "anomaly_score", "thresholds", "recommendation",
                "breached_features", "trend_features"):
        assert key in abn, f"missing {key}"
    approx(abn["anomaly_score"], 0.0, 100.0)
    assert abn["breached_features"] or abn["trend_features"], "degraded asset shows no evidence"


# ---- IN-01: delay logs -----------------------------------------------------
@suite.case
def test_IN01_delay_history():
    d = T.delay_history_tool("GEARBOX-05")
    assert d["events"] > 0 and d["total_downtime_min"] > 0, d
    assert d["tonnage_lost"] >= 0 and d["top_causes"], d


# ---- IN-03 / IN-04: incident retrieval + SQL ------------------------------
@suite.case
def test_IN03_IN04_incident_evidence():
    res = T.rag_tool("seal failure root cause resolution", asset_id="PUMP-12", k=6)["results"]
    incs = [h for h in res if h["type"] == "incident"]
    assert incs, "no incident chunk retrieved"
    assert "root cause" in incs[0]["text"].lower() or "resolution" in incs[0]["text"].lower()
    sql = T.sql_query_tool("SELECT incident_id, title FROM incidents WHERE asset_id='PUMP-12'")
    assert sql.get("row_count", 0) >= 1 and "error" not in sql, sql


# ---- IN-08 / OUT-10 source: manual/SOP retrievable ------------------------
@suite.case
def test_IN08_manual_retrieval():
    res = T.rag_tool("safety isolation repair procedure", asset_id="HYD-VALVE-07", k=6)["results"]
    assert any(h["type"] == "manual" for h in res), "no manual/SOP section returned"


# ---- IN-11 / OUT-14: inventory + constraint flag --------------------------
@suite.case
def test_IN11_inventory_and_constraint():
    inv = T.inventory_tool("GEARBOX-05")["parts"]
    assert inv, "no parts mapped"
    for p in inv:
        assert {"qty_on_hand", "status", "lead_time_days", "unit_cost_usd"} <= set(p)
    risk = T.risk_score_tool("GEARBOX-05")
    assert risk.get("constraint_flag"), "expected lead-time>RUL constraint flag on GEARBOX-05"
    assert "lead" in risk["constraint_flag"].lower() and "rul" in risk["constraint_flag"].lower()


# ---- OUT-06: risk classification over all assets --------------------------
@suite.case
def test_OUT06_risk_bands_all_assets():
    for aid in ASSET_IDS:
        r = T.risk_score_tool(aid)
        approx(r["priority_score"], 0.0, 100.0)
        assert r["priority_band"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}, (aid, r["priority_band"])


# ---- OUT-09: prioritization components ------------------------------------
@suite.case
def test_OUT09_priority_components():
    comp = T.risk_score_tool("GEARBOX-05")["components"]
    assert {"rul_score", "criticality_score", "delay_score", "spares_score"} == set(comp), comp


# ---- FR-06 / IN-10 / OE-04: feedback loop ---------------------------------
@suite.case
def test_FR06_feedback_loop():
    with sandbox():
        base = T.risk_score_tool("PUMP-12")["priority_score"]
        out = T.record_feedback("PUMP-12", note="seal weep recurred",
                                correction="root cause was mechanical seal, not bearing",
                                severity_adjust=20, outcome="reopened")
        assert out["recorded"] and out["feedback_count"] == 1, out
        assert os.path.exists(C.FEEDBACK_CSV), "feedback not persisted"
        b, n = T.learned_bias("PUMP-12")
        assert n == 1 and b > 0, (b, n)
        # default: priority score unaffected (bias gated off)
        assert T.risk_score_tool("PUMP-12")["priority_score"] == base, "score changed though bias gated"
        # OE-04: feedback retrievable for same asset, not bleeding to others
        hits = T.rag_tool("seal weep recurred root cause", asset_id="PUMP-12", k=6)["results"]
        assert any(h["type"] == "feedback" for h in hits), "feedback not retrievable after reindex"
        other = T.rag_tool("seal weep", asset_id="CRANE-06", k=6)["results"]
        assert not any(h["type"] == "feedback" for h in other), "feedback bled to unrelated asset"


# ---- FR-07 / OUT-16: alert dispatch dry-run, live, dedup ------------------
@suite.case
def test_FR07_alert_dispatch_and_dedup():
    with sandbox():
        path = os.path.join(C.DATA_DIR, "notifications.jsonl")
        dry = T.alert_dispatch_tool("GEARBOX-05", "CRITICAL", "test", dry_run=True)
        assert dry["dispatched"] is False and not os.path.exists(path), "dry-run wrote a file"
        live = T.alert_dispatch_tool("GEARBOX-05", "CRITICAL", "test")
        assert live["dispatched"] is True, live
        for key in ("ts", "asset_id", "risk_level", "summary", "recipients"):
            assert key in live, f"alert missing {key}"
        again = T.alert_dispatch_tool("GEARBOX-05", "CRITICAL", "test")
        assert again["dispatched"] is False and again.get("deduped"), "same-day duplicate not deduped"
        assert sum(1 for _ in open(path)) == 1, "expected exactly one notification row"


# ---- OUT-18: digital logbook + closure gating -----------------------------
@suite.case
def test_OUT18_logbook_closure_gating():
    blocked = T.task_closure_tool("WO-1", {"parts_recorded": True})
    assert blocked["can_close"] is False and blocked["completion_blocked_by"], blocked
    full = {k: True for k in T.CLOSURE_ITEMS}
    ok = T.task_closure_tool("WO-1", full)
    assert ok["can_close"] is True and not ok["completion_blocked_by"], ok
    with sandbox():
        T.append_logbook({"timestamp": "t", "work_order_id": "WO-1", "asset_id": "GEARBOX-05",
                          "notes": "done", "closed_by": "engineer"})
        df = pd.read_csv(C.LOGBOOK_CSV)
        assert (df["work_order_id"] == "WO-1").any() and (df["asset_id"] == "GEARBOX-05").any()


# ---- OE-06: user-role-based alerts ----------------------------------------
@suite.case
def test_OE06_role_based_alerts():
    # explicit role routes to that role's recipient
    sup = T.alert_dispatch_tool("GEARBOX-05", "CRITICAL", "t", role="supervisor", dry_run=True)
    assert sup["role"] == "supervisor", sup
    assert sup["recipients"] == C.ALERT_ROLES["supervisor"], sup
    # no recipients/role + CRITICAL band -> auto-routes to supervisor
    auto_crit = T.alert_dispatch_tool("GEARBOX-05", "CRITICAL", "t", dry_run=True)
    assert auto_crit["role"] == "supervisor" and auto_crit["recipients"] == C.ALERT_ROLES["supervisor"]
    # low/medium band -> maintenance team
    auto_low = T.alert_dispatch_tool("CRANE-06", "MEDIUM", "t", dry_run=True)
    assert auto_low["role"] == "maintenance" and auto_low["recipients"] == C.ALERT_ROLES["maintenance"]
    # explicit recipients still honored (backward compatible)
    expl = T.alert_dispatch_tool("PUMP-12", "HIGH", "t", recipients="ops@plant.local", dry_run=True)
    assert expl["recipients"] == "ops@plant.local", expl


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
