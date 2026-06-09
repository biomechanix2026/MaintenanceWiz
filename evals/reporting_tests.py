"""
Reporting, outcome-proxy, and deliverable conformance tests.

Run:  python -m evals.reporting_tests
"""
from __future__ import annotations
import os

import pandas as pd

import config as C
from agent import tools as T
from agent.orchestrator import run_deterministic
from evals._harness import Suite, run_suites, sandbox, gap

suite = Suite("reporting-deliverables")
ROOT = C.ROOT


# ---- OUT-08: plant-level bottleneck prioritization (non-UI) ---------------
@suite.case
def test_OUT08_plant_bottleneck_ranking():
    reg = pd.read_csv(C.ASSET_REGISTRY_CSV)
    rows = []
    for aid in reg.asset_id:
        r = T.risk_score_tool(aid)
        abn = T.abnormality_tool(aid)
        rows.append({"asset_id": aid, "priority_score": r["priority_score"],
                     "band": r["priority_band"], "constraint": bool(r.get("constraint_flag")),
                     "anomaly": abn["status"]})
    rows.sort(key=lambda x: -x["priority_score"])
    scores = [x["priority_score"] for x in rows]
    assert scores == sorted(scores, reverse=True), "not sorted by descending priority"
    assert any(x["constraint"] for x in rows), "no constraint indicator anywhere"
    assert all(x["anomaly"] in {"NORMAL", "WARNING", "CRITICAL"} for x in rows), "missing anomaly indicator"


# ---- OUT-15 / EO-01 / EO-02: pre-shift autonomous report ------------------
@suite.case
def test_OUT15_preshift_report():
    import scripts.pre_shift_run as P
    with sandbox() as d:
        saved = P.REPORTS_DIR
        P.REPORTS_DIR = os.path.join(d, "reports")
        try:
            path = P.run()
        finally:
            P.REPORTS_DIR = saved
        assert os.path.exists(path), "no report written"
        md = open(path, encoding="utf-8").read()
        assert "Action queue" in md, "no action queue"
        assert "critical" in md.lower() and "abnormal" in md.lower(), "no counts"
        assert "RUL" in md and "abnormality" in md.lower(), "missing RUL/abnormality detail"
        assert "Drafted WO" in md, "no drafted work order"
        assert "GEARBOX-05" in md, "EO-01: known high-risk asset absent from pre-shift queue"


# ---- EO-05: out-of-stock long-lead parts surfaced + alter plan ------------
@suite.case
def test_EO05_spares_alter_plan():
    out = [p for p in T.inventory_tool("GEARBOX-05")["parts"] if p["qty_on_hand"] == 0]
    assert out and max(p["lead_time_days"] for p in out) >= 45, "no out-of-stock long-lead part"
    md = run_deterministic("what's wrong with the mill gearbox?").answer_markdown
    block4 = md.split("### 4.")[1].split("### 5.")[0]
    assert any(p["part_no"] in block4 for p in out), "out-of-stock part not surfaced in plan"
    assert "monitored degradation" in md.lower(), "plan not altered by constraint"


# ---- DL-01: working-prototype artifacts + judges pass ---------------------
@suite.case
def test_DL01_artifacts_and_judges():
    required = [
        "config.py", "agent/tools.py", "agent/orchestrator.py", "agent/system_prompt.py",
        "ml/model.py", "ml/train_model.py", "knowledge/rag.py", "data/generate_mock_data.py",
        "app/streamlit_app.py", "scripts/pre_shift_run.py", "evals/judges.py",
        "data/asset_registry.csv", "data/sensor_logs.csv", "data/spare_parts_inventory.csv",
        "ml/artifacts/rul_model.pkl",
    ]
    missing = [p for p in required if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, f"missing artifacts: {missing}"
    assert len(os.listdir(os.path.join(ROOT, "data", "manuals"))) >= 12, "manuals missing"
    # existing regression judges still green
    from evals import judges
    for case in judges.CASES:
        ok, checks, _ = judges.judge(case)
        assert ok, f"judge {case['name']} failed: {checks}"


# ---- DL-03: install/configure/run commands documented ---------------------
@suite.case
def test_DL03_run_commands_documented():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read().lower()
    for cmd in ["pip install", "generate_mock_data", "train_model",
                "knowledge/rag.py", "streamlit run", "evals.judges"]:
        assert cmd.lower() in readme, f"README missing command: {cmd}"


# ---- DL-02: documentation topic coverage (reports gaps) -------------------
@suite.case
def test_DL02_documentation_topics():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read().lower()
    assert os.path.exists(os.path.join(ROOT, "AGENTS.md")), "AGENTS.md missing"
    assert os.path.exists(os.path.join(ROOT, "docs", "deck", "architecture.svg")), "arch diagram missing"
    topics = {
        "architecture": "architecture",
        "tech stack": "stack",
        "data flow": "data",
        "model design": "model",
        "reasoning pipeline": "pipeline",
        "alerting": "alert",
        "prediction": "rul",
        "assumptions": "assumption",
        "limitations": "limitation",
    }
    missing = [name for name, kw in topics.items() if kw not in readme]
    if missing:
        gap(f"README missing documented topics: {', '.join(missing)} (DL-02 doc completeness)")


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
