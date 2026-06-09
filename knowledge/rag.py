"""
Asset-centric RAG layer.

Every chunk of knowledge (manual/SOP sections, historical incidents, delay-log
summaries) is stored with an `asset_id` in its metadata, so retrieval can be
filtered to the exact component being diagnosed - no cross-asset bleed.

Production path:  ChromaDB persistent collection with embeddings.
Fallback path:    a numpy TF-IDF cosine index (zero extra dependencies).
Both expose the same `query(text, asset_id=None, k=4)` interface and the same
result shape, so the agent tools never care which backend is live.
"""
from __future__ import annotations
import os
import re
import sys
import glob
import math
import pickle
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (MANUALS_DIR, INCIDENTS_CSV, DELAY_LOGS_CSV,
                    VECTORSTORE_DIR, FEEDBACK_CSV)

_TFIDF_PATH = os.path.join(VECTORSTORE_DIR, "tfidf_index.pkl")


# --------------------------------------------------------------------------
# Build the corpus of asset-tagged chunks from all knowledge sources.
# --------------------------------------------------------------------------
def build_chunks() -> list[dict]:
    chunks: list[dict] = []

    # 1. Manuals / SOPs - split on markdown "##" sections.
    for path in sorted(glob.glob(os.path.join(MANUALS_DIR, "*.md"))):
        asset_id = os.path.splitext(os.path.basename(path))[0]
        text = open(path, encoding="utf-8").read()
        sections = re.split(r"\n(?=## )", text)
        for sec in sections:
            sec = sec.strip()
            if len(sec) < 40:
                continue
            title = sec.splitlines()[0].lstrip("# ").strip()
            chunks.append({
                "id": f"{asset_id}::{title[:40]}",
                "asset_id": asset_id,
                "source": f"Manual {asset_id} - {title}",
                "type": "manual",
                "text": sec,
            })

    # 2. Incident / failure-analysis records.
    if os.path.exists(INCIDENTS_CSV):
        for _, r in pd.read_csv(INCIDENTS_CSV).iterrows():
            chunks.append({
                "id": r["incident_id"],
                "asset_id": r["asset_id"],
                "source": f"{r['incident_id']} - {r['title']} ({r['date']})",
                "type": "incident",
                "text": (f"Incident {r['incident_id']} on {r['asset_id']}: {r['title']}. "
                         f"Root cause: {r['root_cause']} Resolution: {r['resolution']}"),
            })

    # 3. Delay-log rollups (one summary chunk per asset).
    if os.path.exists(DELAY_LOGS_CSV):
        dl = pd.read_csv(DELAY_LOGS_CSV)
        for aid, g in dl.groupby("asset_id"):
            top = g.groupby("delay_desc")["downtime_min"].sum().sort_values(ascending=False)
            summary = "; ".join(f"{d}: {int(m)} min" for d, m in top.head(3).items())
            chunks.append({
                "id": f"DLY-SUM-{aid}",
                "asset_id": aid,
                "source": f"Delay-log summary {aid}",
                "type": "delay_log",
                "text": (f"Delay history for {aid}: {len(g)} events, "
                         f"{int(g['downtime_min'].sum())} min total downtime, "
                         f"{g['tonnage_lost'].sum():.0f} t lost. Top causes: {summary}."),
            })

    # 4. Engineer feedback (the learning loop): past corrections, confirmations
    #    and outcomes are indexed so a future diagnosis of the same asset
    #    surfaces what the engineer actually said/did last time.
    if os.path.exists(FEEDBACK_CSV):
        for i, r in pd.read_csv(FEEDBACK_CSV).iterrows():
            aid = r.get("asset_id")
            if not isinstance(aid, str) or not aid:
                continue
            parts = [str(r.get(k)) for k in ("correction", "note", "outcome")
                     if isinstance(r.get(k), str) and str(r.get(k)).strip()]
            if not parts:
                continue
            chunks.append({
                "id": f"FB-{aid}-{i}",
                "asset_id": aid,
                "source": f"Engineer feedback {aid} ({r.get('timestamp', '')})",
                "type": "feedback",
                "text": f"Engineer feedback on {aid}: " + " ".join(parts),
            })
    return chunks


# --------------------------------------------------------------------------
# TF-IDF fallback index (numpy only)
# --------------------------------------------------------------------------
def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class TfidfIndex:
    def __init__(self, chunks):
        self.chunks = chunks
        docs = [_tok(c["text"] + " " + c["source"]) for c in chunks]
        df = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, toks):
        tf = Counter(toks)
        v = {t: (cnt / len(toks)) * self.idf.get(t, 0.0) for t, cnt in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def query(self, text, asset_id=None, k=4):
        qv = self._vec(_tok(text))
        scored = []
        for c, dv in zip(self.chunks, self.vecs):
            if asset_id and c["asset_id"] != asset_id:
                continue
            score = sum(qv.get(t, 0) * w for t, w in dv.items())
            scored.append((score, c))
        scored.sort(key=lambda s: -s[0])
        out = []
        for score, c in scored[:k]:
            out.append({**{kk: c[kk] for kk in ("asset_id", "source", "type", "text")},
                        "score": round(float(score), 4)})
        return out


# --------------------------------------------------------------------------
# Unified RAG facade
# --------------------------------------------------------------------------
class RAG:
    def __init__(self, backend, kind):
        self.backend = backend
        self.kind = kind

    def query(self, text, asset_id=None, k=4):
        return self.backend.query(text, asset_id=asset_id, k=k)


def _build_chroma(chunks):
    import chromadb
    os.makedirs(VECTORSTORE_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=VECTORSTORE_DIR)
    try:
        client.delete_collection("maintenance")
    except Exception:
        pass
    col = client.create_collection("maintenance")
    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{"asset_id": c["asset_id"], "source": c["source"], "type": c["type"]}
                   for c in chunks],
    )

    class _ChromaBackend:
        def query(self, text, asset_id=None, k=4):
            where = {"asset_id": asset_id} if asset_id else None
            res = col.query(query_texts=[text], n_results=k, where=where)
            out = []
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0],
                                       res["distances"][0]):
                out.append({"asset_id": meta["asset_id"], "source": meta["source"],
                            "type": meta["type"], "text": doc,
                            "score": round(1 - dist, 4)})
            return out
    return _ChromaBackend()


def build_index(prefer_chroma=True) -> RAG:
    chunks = build_chunks()
    if prefer_chroma:
        try:
            return RAG(_build_chroma(chunks), "chromadb")
        except Exception as e:
            print(f"[info] ChromaDB unavailable ({type(e).__name__}); using TF-IDF fallback.")
    idx = TfidfIndex(chunks)
    os.makedirs(VECTORSTORE_DIR, exist_ok=True)
    with open(_TFIDF_PATH, "wb") as f:
        pickle.dump(idx, f)
    return RAG(idx, "tfidf")


def load_index() -> RAG:
    """Load a previously built index, preferring Chroma, else TF-IDF, else build."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=VECTORSTORE_DIR)
        client.get_collection("maintenance")
        return build_index(prefer_chroma=True)
    except Exception:
        pass
    if os.path.exists(_TFIDF_PATH):
        try:
            with open(_TFIDF_PATH, "rb") as f:
                return RAG(pickle.load(f), "tfidf")
        except Exception:
            pass  # stale/incompatible pickle -> rebuild below
    return build_index(prefer_chroma=False)


if __name__ == "__main__":
    rag = build_index()
    print(f"Built RAG index ({rag.kind}) with {len(build_chunks())} chunks.")
    for r in rag.query("bearing vibration seizure", asset_id="CONV-BELT-03", k=3):
        print(f"  [{r['score']}] {r['source']}")
