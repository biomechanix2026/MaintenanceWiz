"""
Conformance tests for the MW2 -> MW1 ports (hybrid retrieval, citations,
fault classifier, C-MAPSS benchmark).

Run:  python -m evals.port_tests
"""
from __future__ import annotations
import os

from evals._harness import Suite, run_suites, gap

suite = Suite("mw2-ports")

_CHUNKS = [
    {"asset_id": "A1", "source": "Manual A1 - Lube", "type": "manual",
     "text": "Gearbox lubrication: check oil level and viscosity weekly."},
    {"asset_id": "A1", "source": "INC-1 - Pinion wear", "type": "incident",
     "text": "Pinion tooth wear caused vibration; root cause lubrication starvation."},
    {"asset_id": "B2", "source": "Manual B2 - Pump", "type": "manual",
     "text": "Pump impeller inspection procedure and seal replacement torque."},
]


@suite.case
def test_P3_bm25_ranking_and_filter():
    from knowledge.rag import BM25Index
    idx = BM25Index(_CHUNKS)
    hits = idx.query("pinion vibration lubrication", k=2)
    assert hits, "BM25 returned nothing"
    assert hits[0]["source"].startswith("INC-1"), f"expected incident first, got {hits[0]['source']}"
    only_b2 = idx.query("inspection", asset_id="B2", k=4)
    assert only_b2 and all(h["asset_id"] == "B2" for h in only_b2), "asset filter broken"
    assert idx.query("pinion vibration lubrication", asset_id="B2", k=4) == [], "asset filter leaked A1 hits"
    for h in hits:
        assert set(h) == {"asset_id", "source", "type", "text", "score"}, "result shape drifted"
        assert isinstance(h["score"], float), "score should be float"


@suite.case
def test_P3_hybrid_rrf_fusion():
    from knowledge.rag import BM25Index, TfidfIndex, HybridIndex
    hy = HybridIndex(TfidfIndex(_CHUNKS), BM25Index(_CHUNKS), "tfidf")
    assert hy.kind == "hybrid(tfidf+bm25)", hy.kind
    hits = hy.query("pinion vibration root cause", k=3)
    assert hits and hits[0]["source"].startswith("INC-1"), hits
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True), "not sorted by fused score"
    only_a1 = hy.query("lubrication", asset_id="A1", k=4)
    assert only_a1 and all(h["asset_id"] == "A1" for h in only_a1), "asset filter broken in fusion"


@suite.case
def test_P3_live_index_is_hybrid():
    from knowledge.rag import load_index
    rag = load_index()
    assert rag.kind.startswith("hybrid("), f"live index not hybrid: {rag.kind}"
    hits = rag.query("isolation repair procedure", asset_id="GEARBOX-05", k=4)
    assert hits and all(h["asset_id"] == "GEARBOX-05" for h in hits)
    for h in hits:
        assert {"asset_id", "source", "type", "text", "score"} <= set(h)


@suite.case
def test_P4_citation_doc_blocks():
    from agent.orchestrator import _doc_blocks_from_rag
    blocks = _doc_blocks_from_rag([
        {"asset_id": "GEARBOX-05", "source": "Manual GEARBOX-05 - Isolation",
         "type": "manual", "text": "1. Lock out drive. 2. Vent hydraulics.", "score": 0.9},
    ])
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "document" and b["citations"] == {"enabled": True}
    assert b["source"]["data"].startswith("1. Lock out drive")
    assert b["title"] == "Manual GEARBOX-05 - Isolation"
    assert "GEARBOX-05" in b["context"]


def _ai4i_fixture():
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(0)
    n = 200
    torque = rng.normal(40, 10, n)
    wear = rng.uniform(0, 250, n)
    osf = ((torque * wear) > 11000).astype(int)
    df = pd.DataFrame({
        "Type": rng.choice(["L", "M", "H"], n),
        "Air temperature [K]": rng.normal(300, 2, n),
        "Process temperature [K]": rng.normal(310, 1, n),
        "Rotational speed [rpm]": rng.normal(1500, 100, n),
        "Torque [Nm]": torque,
        "Tool wear [min]": wear,
        "TWF": 0, "HDF": 0, "PWF": 0, "RNF": 0,
        "OSF": osf,
    })
    df["Machine failure"] = df[["TWF", "HDF", "PWF", "OSF", "RNF"]].max(axis=1)
    return df


@suite.case
def test_P2_fault_classifier_train_and_classify():
    try:
        import sklearn  # noqa: F401
    except ImportError:
        gap("sklearn not installed - fault classifier rung unavailable here")
    from ml.fault import train_fault_model, classify_fault, MODES
    bundle = train_fault_model(_ai4i_fixture())
    res = classify_fault(bundle, {
        "Type": "M", "Air temperature [K]": 300.0, "Process temperature [K]": 310.0,
        "Rotational speed [rpm]": 1500.0, "Torque [Nm]": 60.0, "Tool wear [min]": 240.0,
    })
    assert 0.0 <= res["risk"] <= 1.0, res
    assert set(res["probs"]) == set(MODES), res
    assert res["probable_mode"] == "OSF", f"high torque*wear should be OSF, got {res}"


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
