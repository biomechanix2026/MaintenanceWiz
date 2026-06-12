"""Export slim demo assets for the Vercel-hosted Gemini demo into web/data/.

Run AFTER the data pipeline (generate_mock_data -> train_model -> rag build).
Everything is exported from the real tool suite (agent.orchestrator.TOOL_SCHEMAS,
agent.tools.*, knowledge.rag.build_chunks) so the hosted demo cannot drift from
the local implementation.

The hosted demo exposes 10 of the 12 tools. Excluded:
- fault_mode_tool  (needs the optional sklearn fault_model.pkl artifact)
- feedback_tool    (persists to CSV + reindexes; writes don't survive a
                    stateless serverless instance)
alert_dispatch_tool is exported but the serverless core forces dry_run.

Run:  python -m scripts.build_demo_assets
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from agent.orchestrator import TOOL_SCHEMAS
from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import prognostic_tool, abnormality_tool, risk_score_tool
from knowledge.rag import build_chunks

WEB_DATA = os.path.join(C.ROOT, "web", "data")
EXCLUDED_TOOLS = {"fault_mode_tool", "feedback_tool"}

DEMO_NOTE = """

# Hosted-demo deployment note
This is the slim hosted build. Differences from the full local build:
- prognostic_tool, abnormality_tool and risk_score_tool return a snapshot
  computed from the latest sensor readings at export time.
- fault_mode_tool and feedback_tool exist only in the full local build;
  never reference or promise them.
- alert_dispatch_tool always runs dry-run here: report the routed alert and
  say live dispatch is disabled in the hosted demo.
- Retrieval is keyword (BM25) only. Name the source document/section for
  every fact you take from rag_tool results.
"""


def demo_tools() -> list[dict]:
    """Anthropic TOOL_SCHEMAS -> Gemini FunctionDeclaration dicts."""
    return [{"name": t["name"], "description": t["description"],
             "parameters": t["input_schema"]}
            for t in TOOL_SCHEMAS if t["name"] not in EXCLUDED_TOOLS]


def build_snapshot(asset_ids: list[str]) -> dict:
    return {"generated": datetime.now(timezone.utc).isoformat(),
            "assets": {aid: {"prognostic": prognostic_tool(aid),
                             "abnormality": abnormality_tool(aid),
                             "risk": risk_score_tool(aid)}
                       for aid in asset_ids}}


def validate_snapshot(snap: dict, asset_ids: list[str]) -> None:
    """Raise ValueError if the snapshot is unusable for the demo."""
    constraint_seen = False
    for aid in asset_ids:
        entry = snap.get("assets", {}).get(aid)
        if entry is None:
            raise ValueError(f"snapshot missing asset {aid}")
        for key in ("prognostic", "abnormality", "risk"):
            if "error" in entry.get(key, {}):
                raise ValueError(f"{aid} {key} errored: {entry[key]['error']}")
        if not entry["prognostic"]["rul_days"] > 0:
            raise ValueError(f"{aid} rul_days not positive")
        score = entry["risk"]["priority_score"]
        if not 0 <= score <= 100:
            raise ValueError(f"{aid} priority_score out of range: {score}")
        constraint_seen = constraint_seen or bool(entry["risk"]["constraint_flag"])
    if not constraint_seen:
        raise ValueError("no asset carries a constraint_flag - the "
                         "lead-time-exceeds-RUL demo centerpiece is missing")


def build_db(path: str) -> None:
    """File-backed copy of agent.tools.Database (same table names)."""
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    for name, csv in [("assets", C.ASSET_REGISTRY_CSV),
                      ("sensors", C.SENSOR_LOGS_CSV),
                      ("delays", C.DELAY_LOGS_CSV),
                      ("incidents", C.INCIDENTS_CSV),
                      ("parts", C.PARTS_CSV)]:
        pd.read_csv(csv).to_sql(name, conn, index=False, if_exists="replace")
    conn.close()


def main() -> None:
    os.makedirs(WEB_DATA, exist_ok=True)
    asset_ids = list(pd.read_csv(C.ASSET_REGISTRY_CSV)["asset_id"])

    snap = build_snapshot(asset_ids)
    validate_snapshot(snap, asset_ids)
    with open(os.path.join(WEB_DATA, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)

    with open(os.path.join(WEB_DATA, "tools.json"), "w", encoding="utf-8") as f:
        json.dump(demo_tools(), f, indent=2)

    with open(os.path.join(WEB_DATA, "system_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(SYSTEM_PROMPT + DEMO_NOTE)

    # exclude feedback chunks: local runtime data must not ship in the demo
    chunks = [c for c in build_chunks() if c["type"] != "feedback"]
    with open(os.path.join(WEB_DATA, "bm25_chunks.jsonl"), "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")

    with open(C.ALIASES_JSON, encoding="utf-8") as src, \
         open(os.path.join(WEB_DATA, "aliases.json"), "w", encoding="utf-8") as dst:
        dst.write(src.read())

    build_db(os.path.join(WEB_DATA, "maintenance.db"))
    print(f"wrote demo assets for {len(asset_ids)} assets, "
          f"{len(chunks)} chunks -> {WEB_DATA}")


if __name__ == "__main__":
    main()
