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


if __name__ == "__main__":
    raise SystemExit(run_suites(suite))
