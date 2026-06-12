# Hackathon Submission + GitHub + Vercel Demo — Implementation Plan (MaintenanceWiz_1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a complete "AI Hackathon — Agentic AI Challenge" submission for this repo (`MaintenanceWiz_1`): a live web demo on vercel.app driven by Gemini's free tier, the repo published to GitHub, submission text, screenshots, and a source zip — with zero LLM API spend.

**Architecture:** The hosted demo is a slim, stateless serverless variant in `web/`: one Vercel Python function (`web/api/chat.py`) running a Gemini 2.5 Flash function-calling loop over **10 of this repo's 12 tools** (excluded: `fault_mode_tool` — needs the optional sklearn artifact; `feedback_tool` — persistent writes don't survive serverless instances; `alert_dispatch_tool` is forced dry-run). Retrieval is BM25-only (the stdlib `BM25Index` already in `knowledge/rag.py`, copied verbatim — no extra dependency). `prognostic_tool`/`abnormality_tool`/`risk_score_tool` serve a precomputed snapshot; `inventory_tool`/`delay_history_tool`/`sql_query_tool` run read-only SQL over a bundled SQLite file built from the repo's CSVs. A build script (`scripts/build_demo_assets.py`) exports everything from the real tool suite (`agent.orchestrator.TOOL_SCHEMAS`, `agent.tools.*`, `knowledge.rag.build_chunks`) so the demo cannot drift from the local implementation. Conversation history is carried by the browser.

**Tech Stack:** Python stdlib `BaseHTTPRequestHandler` + `google-genai` on the server (no pandas/numpy in the function), vanilla-JS single-page chat UI, Vercel Python runtime, GitHub via `gh` CLI.

**Decisions reconciled from the review of the original (MaintenanceWiz_2) plan:**
- **No doc-corpus authoring task.** `data/manuals/*.md` already exists for all 12 assets and is tracked in git. The original plan's biggest task is dropped entirely.
- **Real asset IDs.** Demo examples use the eval-proven queries (`GEARBOX-05` constraint-flag scenario, `HYD-VALVE-07` fuzzy resolution, `CRANE-06` healthy baseline, `FURNACE-01` "EAF" jargon). No `EQ-00x` anywhere.
- **Export from real APIs.** `TOOL_SCHEMAS` (not a nonexistent `tools.TOOLS`), `prognostic_tool`/`abnormality_tool`/`risk_score_tool` (not nonexistent `get_equipment_health`), `build_chunks()` (not `rag/ingest.py`).
- **Verification is `python -m evals.judges`** (the repo's regression guard) plus a new plain-assert module `evals/demo_tests.py` run as `python -m evals.demo_tests`. No pytest dependency is introduced.
- **Gitignore reality:** this repo's `.gitignore` ignores none of what the old plan assumed. Hygiene steps below operate on what is actually tracked (notably `knowledge/store/` binaries).
- **Existing deck is reused.** `docs/deck/MaintenanceWizard.pptx` already exists (with PDF + build script) and has uncommitted in-flight edits — this plan does NOT rebuild it.
- **Gemini schema format is verified at execution time** (Step 3.6) before any code depends on it: official `google-genai` uses `types.FunctionDeclaration(..., parameters={...})`; `parameters_json_schema` is the fallback spelling if the installed version rejects raw JSON-schema dicts.

**Constraints discovered during planning (verified against this checkout):**
- 12 tools in `agent/orchestrator.py` `TOOL_FUNCS`/`TOOL_SCHEMAS`; both modes must keep working — this plan never edits them.
- `app/` is hands-off on `codex/mw2-port` (frontend upgrade in flight in another session). The demo UI lives in `web/` — a new directory — so there is no overlap.
- Working tree has uncommitted changes NOT belonging to this plan (`docs/deck/MaintenanceWizard.pptx`, `knowledge/store/*`). **Never `git add -A` / `git add .` — stage explicit paths only.**
- Branches: `codex/mw2-port` (current, 33 ahead of `main`), `main` (0 ahead — fast-forwardable). No git remote exists yet.
- `knowledge/store/` (Chroma binaries + tfidf pickle, ~MBs) IS tracked and churns on every reindex. Untracked in Task 1; `knowledge/rag.py:load_index()` rebuilds automatically when the store is absent, and `python knowledge/rag.py` is already a documented pipeline step.
- `data/feedback.csv` and `data/digital_logbook.csv` are gitignored runtime files; the chunk export must exclude `type == "feedback"` chunks so local test feedback never lands in committed demo data.
- `.env.example` exists; `.env` is ignored. `ml/artifacts/` tracks `benchmark.json`, `feature_columns.json` AND two model pickles (`rul_model.pkl`, `fault_model.pkl`) — the pickles are untracked in Task 1 (sklearn-version-fragile binaries, rebuilt locally by `python ml/train_model.py` / `python -m ml.fault`, both documented pipeline steps).
- Python 3.14 is the local interpreter.

---

## Task 0: Prerequisites (user-interactive)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 0.1: Get a free Gemini API key (USER action)**

Ask the user to create a free key at https://aistudio.google.com/apikey and add `GEMINI_API_KEY=...` to `.env` (file is gitignored). Then verify:

```powershell
python -c "import os; from pathlib import Path; env = dict(l.split('=',1) for l in Path('.env').read_text().splitlines() if '=' in l and not l.startswith('#')); print('KEY OK' if env.get('GEMINI_API_KEY','').strip() else 'KEY MISSING')"
```

Expected: `KEY OK`. (No python-dotenv in this repo — read the file directly.)

- [ ] **Step 0.2: Baseline — the regression guard must pass before any change**

```powershell
python -m evals.judges
```

Expected: all judges pass, exit code 0. If not, STOP and report — do not build on a broken baseline.

- [ ] **Step 0.3: Install google-genai and record it**

```powershell
pip install google-genai
```

Append to `requirements.txt` under the production section:

```text
google-genai   # hosted-demo build (web/): Gemini free-tier function calling
```

- [ ] **Step 0.4: Install CLIs**

```powershell
winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
npm install -g vercel
```

Expected: both install. `gh` needs a NEW shell for PATH — verify `gh --version` and `vercel --version` in a fresh invocation.

---

## Task 1: Branch + repo hygiene

**Files:**
- Modify: `.gitignore`
- Untrack (files stay on disk): `knowledge/store/*`, `ml/artifacts/*.pkl`

- [ ] **Step 1.1: Create the work branch**

```powershell
git checkout -b codex/hackathon-vercel-demo codex/mw2-port
```

Expected: new branch from the current integration branch. The in-flight uncommitted changes (`docs/deck/MaintenanceWizard.pptx`, `knowledge/store/*`) carry over in the working tree — leave them uncommitted.

- [ ] **Step 1.2: Stop tracking the vector store; ignore build outputs**

Append to `.gitignore`:

```gitignore
knowledge/store/
dist/
ml/artifacts/*.pkl
```

Then untrack the rebuildable binaries (files remain on disk):

```powershell
git rm -r --cached knowledge/store
git rm --cached ml/artifacts/rul_model.pkl ml/artifacts/fault_model.pkl
```

Rationale: the store is a rebuildable artifact (`python knowledge/rag.py`) whose binaries churn on every feedback reindex, and the model pickles are sklearn-version-fragile binaries rebuilt by `python ml/train_model.py` / `python -m ml.fault`; publishing them bloats the repo and the source zip. `benchmark.json` and `feature_columns.json` stay tracked (small text artifacts referenced by `prognostic_tool`).

- [ ] **Step 1.3: Verify the fallback path still works without a tracked store**

```powershell
python -m evals.judges
```

Expected: all pass (the store still exists on disk; this proves nothing referenced git-tracked state). Also sanity-check `load_index()` rebuild behavior is documented: `knowledge/rag.py:273-296` falls back TF-IDF → build when no store exists.

- [ ] **Step 1.4: Secret sweep baseline**

```powershell
git ls-files | Select-String -Pattern "\.env$|secret|credential|\.pem|key\.json"
```

Expected: no output. (`data/aliases.json` is plant jargon, not a secret — it stays tracked.)

- [ ] **Step 1.5: Commit**

```powershell
git add .gitignore requirements.txt docs/superpowers/plans/2026-06-12-hackathon-submission-vercel.md
git commit -m "chore: untrack rebuildable binaries (vector store, model pickles); add google-genai dep; add submission plan"
```

Note: the `git rm -r --cached` from Step 1.2 is already staged; this commit includes it.

---

## Task 2: Demo-asset export script

**Files:**
- Create: `scripts/build_demo_assets.py`
- Create: `evals/demo_tests.py` (plain-assert tests, repo has no pytest)
- Generated (committed): `web/data/snapshot.json`, `web/data/tools.json`, `web/data/system_prompt.txt`, `web/data/aliases.json`, `web/data/bm25_chunks.jsonl`, `web/data/maintenance.db`

- [ ] **Step 2.1: Write the failing tests**

Create `evals/demo_tests.py`:

```python
"""Focused tests for the hosted-demo export script and serverless core.

Plain-assert style (this repo has no pytest; `python -m evals.judges` is the
regression guard and this module is its sibling for the web demo).

Run:  python -m evals.demo_tests
"""
from __future__ import annotations
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Export script (scripts/build_demo_assets.py) — pure parts only
# ---------------------------------------------------------------------------
def _good_snapshot(asset_ids):
    return {"generated": "2026-06-12T00:00:00+00:00",
            "assets": {aid: {
                "prognostic": {"asset_id": aid, "rul_days": 50.0,
                               "failure_probability_30d": 0.2, "shap": {}},
                "abnormality": {"asset_id": aid, "status": "NORMAL",
                                "anomaly_score": 10.0},
                "risk": {"asset_id": aid, "priority_score": 40.0,
                         "priority_band": "MEDIUM", "constraint_flag": None},
            } for aid in asset_ids}}


def test_demo_tools_subset_and_gemini_format():
    from scripts.build_demo_assets import demo_tools, EXCLUDED_TOOLS
    from agent.orchestrator import TOOL_FUNCS, TOOL_SCHEMAS
    tools = demo_tools()
    names = {t["name"] for t in tools}
    assert EXCLUDED_TOOLS == {"fault_mode_tool", "feedback_tool"}
    assert names.isdisjoint(EXCLUDED_TOOLS)
    assert len(tools) == len(TOOL_SCHEMAS) - len(EXCLUDED_TOOLS)  # 10 of 12
    assert names <= set(TOOL_FUNCS)            # every exported tool is real
    for t in tools:                            # Gemini format, not Anthropic
        assert "parameters" in t and "input_schema" not in t
        assert t["parameters"]["type"] == "object"


def test_validate_snapshot_accepts_good():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1", "B-2"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "LEAD TIME EXCEEDS RUL"
    validate_snapshot(snap, ["A-1", "B-2"])    # must not raise


def test_validate_snapshot_rejects_missing_asset():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "x"
    try:
        validate_snapshot(snap, ["A-1", "B-2"])
    except ValueError:
        return
    raise AssertionError("missing asset not rejected")


def test_validate_snapshot_rejects_out_of_range_score():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])
    snap["assets"]["A-1"]["risk"]["constraint_flag"] = "x"
    snap["assets"]["A-1"]["risk"]["priority_score"] = 140.0
    try:
        validate_snapshot(snap, ["A-1"])
    except ValueError:
        return
    raise AssertionError("out-of-range score not rejected")


def test_validate_snapshot_requires_constraint_demo():
    from scripts.build_demo_assets import validate_snapshot
    snap = _good_snapshot(["A-1"])             # no constraint_flag anywhere
    try:
        validate_snapshot(snap, ["A-1"])
    except ValueError:
        return
    raise AssertionError("snapshot without any constraint_flag not rejected")


# ---------------------------------------------------------------------------
# Serverless core (web/api/_core.py) — tests added in Task 3 below this line
# ---------------------------------------------------------------------------


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except Exception as e:
            failures.append((name, e))
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.2: Run to verify failure**

```powershell
python -m evals.demo_tests
```

Expected: failures with `ModuleNotFoundError: No module named 'scripts.build_demo_assets'`.

- [ ] **Step 2.3: Write the export script**

Create `scripts/build_demo_assets.py`:

```python
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
```

- [ ] **Step 2.4: Run tests to verify they pass**

```powershell
python -m evals.demo_tests
```

Expected: `5/5 passed`, exit 0.

- [ ] **Step 2.5: Generate the assets and sanity-check**

```powershell
python -m scripts.build_demo_assets
Get-ChildItem web\data | Select-Object Name, Length
```

Expected: prints `wrote demo assets for 12 assets, ... chunks`. `web/data` totals a few MB (sensor CSV is only ~90KB, so `maintenance.db` is small). If `validate_snapshot` raises about the missing constraint flag, the local pipeline is stale — rerun `python data/generate_mock_data.py && python ml/train_model.py && python knowledge/rag.py` and retry.

- [ ] **Step 2.6: Commit**

```powershell
git add scripts/build_demo_assets.py evals/demo_tests.py web/data
git commit -m "feat: export slim demo assets for Vercel deployment (Gemini tool format)"
```

Confirm with `git status` that nothing else (deck/store changes) got staged.

---

## Task 3: Serverless demo core (Gemini)

**Files:**
- Create: `web/api/_core.py` (underscore prefix → Vercel does not expose it as a route)
- Modify: `evals/demo_tests.py` (append core tests)

- [ ] **Step 3.1: Append the failing core tests**

Append to `evals/demo_tests.py`, replacing the `# Serverless core ... tests added in Task 3` comment block:

```python
# ---------------------------------------------------------------------------
# Serverless core (web/api/_core.py)
# ---------------------------------------------------------------------------
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _core():
    spec = importlib.util.spec_from_file_location(
        "demo_core", _ROOT / "web" / "api" / "_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CHUNKS = [
    {"id": "c1", "asset_id": "GEARBOX-05",
     "source": "Manual GEARBOX-05 - Troubleshooting", "type": "manual",
     "text": "bearing vibration high on gearbox pinion"},
    {"id": "c2", "asset_id": "PUMP-12",
     "source": "Manual PUMP-12 - Troubleshooting", "type": "manual",
     "text": "bearing vibration inspection procedure for pump"},
]


def test_core_rag_filters_by_asset():
    dc = _core()
    dc._cache["chunks"] = _CHUNKS
    dc._cache.pop("bm25", None)
    out = dc.rag_tool("bearing vibration", asset_id="PUMP-12")
    assert [h["source"] for h in out["results"]] == [_CHUNKS[1]["source"]]
    assert out["backend"].startswith("bm25")


def test_core_snapshot_tools_and_unknown_asset():
    dc = _core()
    dc._cache["snapshot"] = {"assets": {"GEARBOX-05": {
        "prognostic": {"rul_days": 12.0}, "abnormality": {"status": "CRITICAL"},
        "risk": {"priority_score": 85.0, "constraint_flag": "LEAD TIME"}}}}
    assert dc.prognostic_tool("GEARBOX-05")["rul_days"] == 12.0
    assert "error" in dc.prognostic_tool("NO-SUCH-99")


def test_core_dispatch_search_returns_sources():
    dc = _core()
    dc._cache["chunks"] = _CHUNKS
    dc._cache.pop("bm25", None)
    result, sources = dc.dispatch("rag_tool", {"query": "bearing vibration"})
    assert result["results"] and sources
    assert sources[0]["source"].startswith("Manual ")


def test_core_dispatch_unknown_tool():
    dc = _core()
    result, sources = dc.dispatch("no_such_tool", {})
    assert "error" in result and sources is None


def test_core_alert_is_always_dry_run():
    dc = _core()
    out, _ = dc.dispatch("alert_dispatch_tool", {
        "asset_id": "GEARBOX-05", "risk_level": "CRITICAL", "summary": "x"})
    assert out["dry_run"] is True and out["dispatched"] is False
    assert out["recipients"] == "shift-supervisor@plant.local"


def test_core_sql_guard_rejects_writes():
    dc = _core()
    out, _ = dc.dispatch("sql_query_tool", {"sql": "DELETE FROM parts"})
    assert "error" in out


def test_core_task_closure_pure():
    dc = _core()
    out, _ = dc.dispatch("task_closure_tool", {"work_order_id": "WO-1"})
    assert out["can_close"] is False and out["completion_blocked_by"]


def test_core_rate_limiter():
    dc = _core()
    dc._hits.clear()
    now = 1000.0
    for _ in range(dc.RATE_LIMIT):
        assert dc.rate_limited("1.2.3.4", now=now) is False
    assert dc.rate_limited("1.2.3.4", now=now) is True
    assert dc.rate_limited("5.6.7.8", now=now) is False
    assert dc.rate_limited("1.2.3.4", now=now + dc.RATE_WINDOW + 1) is False
```

- [ ] **Step 3.2: Run to verify failure**

```powershell
python -m evals.demo_tests
```

Expected: the 5 export tests pass; all `test_core_*` fail with `FileNotFoundError` (no `web/api/_core.py`).

- [ ] **Step 3.3: Write the core module**

Create `web/api/_core.py`:

```python
"""Slim serverless core for the hosted Maintenance Wizard demo (Gemini).

Differences from the full local build (agent/orchestrator.py + agent/tools.py):
- LLM is Gemini 2.5 Flash via the free AI Studio key (GEMINI_API_KEY), not
  Claude - the public demo must cost nothing to run.
- prognostic/abnormality/risk serve a precomputed snapshot
  (web/data/snapshot.json) exported by scripts/build_demo_assets.py.
- Retrieval is BM25-only over the exported chunk file; BM25Index is copied
  verbatim from knowledge/rag.py (pure stdlib - no extra dependency).
- fault_mode_tool and feedback_tool are not deployed; alert_dispatch_tool is
  forced dry-run (no side effects on a stateless instance).
- SQLite is opened read-only on the bundled file (no writes are needed).
- Stateless: the client sends full message history each request and gets the
  updated history back (google-genai Content dicts).
"""
from __future__ import annotations
import difflib
import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from google import genai
from google.genai import types

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL = os.environ.get("WIZARD_MODEL", "gemini-2.5-flash")
MAX_TOKENS = int(os.environ.get("WIZARD_MAX_TOKENS", "4000"))
MAX_TOOL_ROUNDS = 10
RATE_LIMIT = 20      # requests per IP ...
RATE_WINDOW = 3600   # ... per hour (in-memory, per warm instance)

# Role routing copied from config.ALERT_ROLES (the demo bundles no config.py)
ALERT_ROLES = {
    "maintenance": "maintenance-team@plant.local",
    "reliability": "reliability-engineering@plant.local",
    "supervisor":  "shift-supervisor@plant.local",
}

_cache: dict = {}
_hits: dict[str, list[float]] = {}


def _load(name, loader):
    if name not in _cache:
        _cache[name] = loader()
    return _cache[name]


def _chunks() -> list[dict]:
    return _load("chunks", lambda: [
        json.loads(line) for line in
        (DATA_DIR / "bm25_chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()])


def _snapshot() -> dict:
    return _load("snapshot", lambda: json.loads(
        (DATA_DIR / "snapshot.json").read_text(encoding="utf-8")))


def _aliases() -> dict:
    return _load("aliases", lambda: json.loads(
        (DATA_DIR / "aliases.json").read_text(encoding="utf-8")))


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DATA_DIR / 'maintenance.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rate_limited(ip: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    window = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(window) >= RATE_LIMIT:
        _hits[ip] = window
        return True
    window.append(now)
    _hits[ip] = window
    return False


# --- BM25 (copied verbatim in spirit from knowledge/rag.py BM25Index) -------

def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25Index:
    K1, B = 1.5, 0.75

    def __init__(self, chunks):
        self.chunks = chunks
        self.docs = [_tok(c["text"] + " " + c["source"]) for c in chunks]
        self.doc_len = [len(d) or 1 for d in self.docs]
        self.avg_len = (sum(self.doc_len) / len(self.docs)) if self.docs else 1.0
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def query(self, text, asset_id=None, k=4):
        q = _tok(text)
        scored = []
        for i, c in enumerate(self.chunks):
            if asset_id and c["asset_id"] != asset_id:
                continue
            dl = self.doc_len[i]
            s = 0.0
            for t in q:
                f = self.tf[i].get(t)
                if not f:
                    continue
                s += (self.idf.get(t, 0.0) * f * (self.K1 + 1)
                      / (f + self.K1 * (1 - self.B + self.B * dl / self.avg_len)))
            if s > 0:
                scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        return [{**{kk: c[kk] for kk in ("asset_id", "source", "type", "text")},
                 "score": round(float(s), 4)} for s, c in scored[:k]]


def _bm25() -> BM25Index:
    return _load("bm25", lambda: BM25Index(_chunks()))


# --- tools (same names + result shapes as agent/tools.py) -------------------

def resolve_asset(query: str) -> dict:
    aliases = _aliases()
    with closing(_db()) as conn:
        rows = conn.execute("SELECT asset_id, name FROM assets").fetchall()
    q = query.lower().strip()
    for r in rows:
        if r["asset_id"].lower() in q:
            return {"asset_id": r["asset_id"], "confidence": 1.0,
                    "matched_on": "explicit id"}
    for alias, aid in aliases.items():
        if alias in q:
            return {"asset_id": aid, "confidence": 0.95,
                    "matched_on": f"alias '{alias}'"}
    best = difflib.get_close_matches(q, list(aliases.keys()), n=1, cutoff=0.6)
    if best:
        return {"asset_id": aliases[best[0]], "confidence": 0.75,
                "matched_on": f"fuzzy alias '{best[0]}'"}
    names = {r["name"].lower(): r["asset_id"] for r in rows}
    best = difflib.get_close_matches(q, list(names), n=1, cutoff=0.5)
    if best:
        return {"asset_id": names[best[0]], "confidence": 0.6,
                "matched_on": f"fuzzy name '{best[0]}'"}
    return {"asset_id": None, "confidence": 0.0, "matched_on": None,
            "clarification_needed": True,
            "candidates": [dict(r) for r in rows[:6]]}


def _snap_entry(asset_id: str, key: str) -> dict:
    entry = _snapshot()["assets"].get(asset_id)
    if entry is None:
        known = ", ".join(sorted(_snapshot()["assets"]))
        return {"error": f"No snapshot for {asset_id}. Known assets: {known}"}
    return entry[key]


def prognostic_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "prognostic")


def abnormality_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "abnormality")


def risk_score_tool(asset_id: str) -> dict:
    return _snap_entry(asset_id, "risk")


def rag_tool(query: str, asset_id: str | None = None, k: int = 4) -> dict:
    hits = _bm25().query(query, asset_id=asset_id, k=k)
    return {"query": query, "asset_id": asset_id,
            "backend": "bm25 (hosted demo)", "results": hits}


def inventory_tool(asset_id: str) -> dict:
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT part_no, description, qty_on_hand, lead_time_days, "
            "unit_cost_usd FROM parts WHERE asset_id = ? "
            "ORDER BY (qty_on_hand > 0) ASC, lead_time_days DESC",
            (asset_id,)).fetchall()
    items = [{"part_no": r["part_no"], "description": r["description"],
              "qty_on_hand": int(r["qty_on_hand"]),
              "lead_time_days": int(r["lead_time_days"]),
              "unit_cost_usd": float(r["unit_cost_usd"]),
              "status": ("IN STOCK" if int(r["qty_on_hand"]) > 0 else
                         f"OUT - reorder ({int(r['lead_time_days'])}d lead)")}
             for r in rows]
    return {"asset_id": asset_id, "parts": items}


def delay_history_tool(asset_id: str) -> dict:
    with closing(_db()) as conn:
        agg = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(downtime_min),0) AS mins, "
            "COALESCE(SUM(tonnage_lost),0) AS tons FROM delays "
            "WHERE asset_id = ?", (asset_id,)).fetchone()
        top = conn.execute(
            "SELECT delay_desc, SUM(downtime_min) AS mins FROM delays "
            "WHERE asset_id = ? GROUP BY delay_desc ORDER BY mins DESC LIMIT 3",
            (asset_id,)).fetchall()
    if agg["n"] == 0:
        return {"asset_id": asset_id, "events": 0,
                "total_downtime_min": 0, "tonnage_lost": 0}
    return {"asset_id": asset_id, "events": int(agg["n"]),
            "total_downtime_min": int(agg["mins"]),
            "tonnage_lost": round(float(agg["tons"]), 1),
            "top_causes": {r["delay_desc"]: int(r["mins"]) for r in top}}


def sql_query_tool(sql: str) -> dict:
    """Same read-only guard as agent/tools.py: a single SELECT/WITH statement."""
    s = sql.strip().lower()
    if not (s.startswith("select") or s.startswith("with")):
        return {"sql": sql, "error": "Only read-only SELECT / WITH queries are permitted."}
    if ";" in s.rstrip(";"):
        return {"sql": sql, "error": "Multiple statements are not permitted."}
    try:
        with closing(_db()) as conn:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchmany(2000)]
        return {"sql": sql, "row_count": len(rows), "rows": rows[:50]}
    except Exception as e:
        return {"sql": sql, "error": str(e)}


def _role_for_band(risk_level: str) -> str:
    rl = (risk_level or "").upper()
    if "CRITICAL" in rl:
        return "supervisor"
    if rl == "HIGH":
        return "reliability"
    return "maintenance"


def alert_dispatch_tool(asset_id: str, risk_level: str, summary: str,
                        recipients: str | None = None,
                        role: str | None = None) -> dict:
    """Demo build: ALWAYS dry-run. Routing logic mirrors agent/tools.py."""
    if recipients is None:
        role = role or _role_for_band(risk_level)
        recipients = ALERT_ROLES.get(role, ALERT_ROLES["maintenance"])
    elif role is None:
        role = "explicit"
    return {"dispatched": False, "dry_run": True,
            "note": "live dispatch disabled in the hosted demo",
            "asset_id": asset_id, "risk_level": risk_level, "role": role,
            "summary": summary, "recipients": recipients}


CLOSURE_ITEMS = ["parts_recorded", "steps_logged", "isolation_cleared",
                 "follow_up_scheduled", "digital_logbook_entry"]


def task_closure_tool(work_order_id: str, checklist: dict | None = None) -> dict:
    checklist = checklist or {}
    state = {item: bool(checklist.get(item, False)) for item in CLOSURE_ITEMS}
    missing = [k for k, v in state.items() if not v]
    return {"work_order_id": work_order_id, "checklist": state,
            "completion_blocked_by": missing, "can_close": len(missing) == 0,
            "message": ("Job may be closed - all compliance items satisfied."
                        if not missing else
                        f"Closure BLOCKED. Outstanding: {', '.join(missing)}.")}


TOOL_FUNCS = {
    "resolve_asset": lambda a: resolve_asset(a["query"]),
    "prognostic_tool": lambda a: prognostic_tool(a["asset_id"]),
    "abnormality_tool": lambda a: abnormality_tool(a["asset_id"]),
    "rag_tool": lambda a: rag_tool(a["query"], a.get("asset_id"), a.get("k", 4)),
    "inventory_tool": lambda a: inventory_tool(a["asset_id"]),
    "sql_query_tool": lambda a: sql_query_tool(a["sql"]),
    "delay_history_tool": lambda a: delay_history_tool(a["asset_id"]),
    "risk_score_tool": lambda a: risk_score_tool(a["asset_id"]),
    "alert_dispatch_tool": lambda a: alert_dispatch_tool(
        a["asset_id"], a["risk_level"], a["summary"],
        a.get("recipients"), a.get("role")),
    "task_closure_tool": lambda a: task_closure_tool(
        a["work_order_id"], a.get("checklist")),
}


def dispatch(name: str, args: dict) -> tuple[object, list[dict] | None]:
    """Run one tool. Returns (result, sources) - sources only for rag_tool."""
    func = TOOL_FUNCS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}, None
    try:
        result = func(dict(args or {}))
    except Exception as exc:  # surface to the model, never crash the loop
        return {"error": f"{type(exc).__name__}: {exc}"}, None
    if name == "rag_tool":
        sources = [{"source": h["source"], "type": h["type"],
                    "asset_id": h["asset_id"]} for h in result["results"]]
        return result, sources
    return result, None


# --- stateless wizard loop ---------------------------------------------------

def _tool_config() -> types.Tool:
    return _load("tools", lambda: types.Tool(function_declarations=[
        types.FunctionDeclaration(**t) for t in json.loads(
            (DATA_DIR / "tools.json").read_text(encoding="utf-8"))]))


def _system_prompt() -> str:
    return _load("system", lambda:
                 (DATA_DIR / "system_prompt.txt").read_text(encoding="utf-8"))


def chat_turn(message: str, history: list[dict]) -> tuple[dict, list[dict]]:
    """One stateless turn. Returns (rendered, updated_history)."""
    client = genai.Client()  # reads GEMINI_API_KEY from env
    contents = [types.Content(**c) for c in history]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    config_ = types.GenerateContentConfig(
        system_instruction=_system_prompt(),
        tools=[_tool_config()],
        max_output_tokens=MAX_TOKENS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
    )
    sources: list[dict] = []
    rendered = {"text": "(stopped: tool-round limit reached)",
                "sources": [], "stop_reason": "tool_round_limit"}
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.models.generate_content(
            model=MODEL, contents=contents, config=config_)
        candidate = response.candidates[0]
        contents.append(candidate.content)
        calls = [p.function_call for p in (candidate.content.parts or [])
                 if p.function_call]
        if not calls:
            text = "".join(p.text for p in (candidate.content.parts or [])
                           if p.text)
            rendered = {"text": text, "sources": sources,
                        "stop_reason": str(candidate.finish_reason)}
            break
        parts = []
        for fc in calls:
            result, hit_sources = dispatch(fc.name, dict(fc.args or {}))
            sources.extend(hit_sources or [])
            parts.append(types.Part.from_function_response(
                name=fc.name, response={"result": result}))
        # role="user" is the documented google-genai pattern for returning
        # function responses (verified against the function-calling docs)
        contents.append(types.Content(role="user", parts=parts))
    history_out = [c.model_dump(exclude_none=True, mode="json")
                   for c in contents]
    return rendered, history_out
```

- [ ] **Step 3.4: Run tests to verify they pass**

```powershell
python -m evals.demo_tests
```

Expected: `13/13 passed`, exit 0. Then the regression guard: `python -m evals.judges` — all pass (nothing in `agent/` was touched; this is the safety net).

- [ ] **Step 3.5: Verify the Gemini schema format against the installed google-genai**

```powershell
python -c "import json; from google.genai import types; tools = json.load(open('web/data/tools.json')); tool = types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in tools]); print('SCHEMA OK:', len(tool.function_declarations), 'declarations')"
```

Expected: `SCHEMA OK: 10 declarations`. If `FunctionDeclaration` rejects the `parameters` dict, change `demo_tools()` in `scripts/build_demo_assets.py` to emit the key `parameters_json_schema` instead of `parameters`, rerun `python -m scripts.build_demo_assets`, update the format assertion in `test_demo_tools_subset_and_gemini_format`, and re-verify.

- [ ] **Step 3.6: Live one-shot sanity check against Gemini (1 free call)**

```powershell
$env:GEMINI_API_KEY = (Get-Content .env | Where-Object { $_ -match '^GEMINI_API_KEY=' }) -replace '^GEMINI_API_KEY=',''
python -c "import importlib.util; from pathlib import Path; spec = importlib.util.spec_from_file_location('dc', Path('web/api/_core.py')); dc = importlib.util.module_from_spec(spec); spec.loader.exec_module(dc); r, h = dc.chat_turn('Do we have spares in stock for GEARBOX-05?', []); print(r['text'][:400]); print('SOURCES:', r['sources'][:3]); print('HISTORY LEN:', len(h))"
```

Expected: a grounded answer naming real part numbers from `spare_parts_inventory.csv`; non-empty history. The function-response role is `role="user"` (the documented google-genai pattern); if a future SDK version rejects it, `role="tool"` is the alternate spelling — this one free call catches that cheaply.

- [ ] **Step 3.7: Commit**

```powershell
git add web/api/_core.py evals/demo_tests.py
git commit -m "feat: slim stateless Gemini wizard core for Vercel demo (10 of 12 tools)"
```

---

## Task 4: Vercel function handler

**Files:**
- Create: `web/api/chat.py`

- [ ] **Step 4.1: Write the handler**

Create `web/api/chat.py`:

```python
"""Vercel Python function: POST /api/chat {message, history} ->
{text, sources, stop_reason, history}."""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._core import chat_turn, rate_limited  # noqa: E402

MAX_HISTORY_MESSAGES = 60  # ~10 multi-tool turns; caps token spend


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        ip = self.headers.get("x-forwarded-for", "?").split(",")[0].strip()
        if rate_limited(ip):
            return self._send(429, {
                "error": "Demo rate limit reached (20 requests/hour). "
                         "Please try again later."})
        try:
            length = int(self.headers.get("content-length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            message = (body.get("message") or "").strip()
            history = body.get("history") or []
            if not message:
                return self._send(400, {"error": "message is required"})
            if not isinstance(history, list) or len(history) > MAX_HISTORY_MESSAGES:
                return self._send(400, {
                    "error": "conversation too long - refresh to start over"})
            rendered, messages = chat_turn(message, history)
            self._send(200, {**rendered, "history": messages})
        except Exception as exc:  # demo surface: return the error, don't 502
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
```

- [ ] **Step 4.2: Import smoke test**

```powershell
python -c "import sys; sys.path.insert(0, 'web'); import api.chat; print('handler import OK')"
```

Expected: `handler import OK`.

- [ ] **Step 4.3: Commit**

```powershell
git add web/api/chat.py
git commit -m "feat: Vercel chat endpoint with rate limit and history cap"
```

---

## Task 5: Frontend chat UI

**Files:**
- Create: `web/index.html`

Note: `app/` (Streamlit) is hands-off per the in-flight frontend upgrade; `web/` is a new, independent surface.

- [ ] **Step 5.1: Write the page**

Create `web/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maintenance Wizard — Agentic Maintenance Copilot</title>
<style>
  :root { --bg:#0e1116; --panel:#161b22; --line:#2d333b; --text:#e6edf3;
          --dim:#8b949e; --accent:#e8590c; --user:#1f3a5f; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:15px/1.5 system-ui, "Segoe UI", sans-serif;
         display:flex; flex-direction:column; height:100vh; }
  header { padding:14px 20px; border-bottom:1px solid var(--line);
           display:flex; align-items:baseline; gap:12px; }
  header h1 { font-size:17px; margin:0; }
  header span { color:var(--dim); font-size:13px; }
  #log { flex:1; overflow-y:auto; padding:20px; max-width:860px;
         width:100%; margin:0 auto; }
  .msg { padding:10px 14px; border-radius:10px; margin:8px 0;
         word-wrap:break-word; }
  .user { background:var(--user); margin-left:15%; white-space:pre-wrap; }
  .bot  { background:var(--panel); border:1px solid var(--line);
          margin-right:5%; }
  .bot h3 { font-size:14px; color:var(--accent); margin:12px 0 4px; }
  .bot code { background:#0e1116; padding:1px 5px; border-radius:4px;
              font-size:13px; }
  .bot blockquote { border-left:3px solid var(--accent); margin:6px 0;
                    padding-left:10px; color:var(--dim); }
  .cites { font-size:12.5px; color:var(--dim); border-top:1px dashed
           var(--line); margin-top:8px; padding-top:6px; }
  .cites b { color:var(--accent); }
  .err { color:#f85149; }
  #examples { max-width:860px; margin:0 auto; padding:0 20px 8px;
              display:flex; flex-wrap:wrap; gap:8px; }
  #examples button { background:var(--panel); color:var(--dim);
      border:1px solid var(--line); border-radius:14px; padding:5px 12px;
      cursor:pointer; font-size:13px; }
  #examples button:hover { color:var(--text); border-color:var(--accent); }
  form { display:flex; gap:8px; padding:14px 20px 18px; max-width:860px;
         width:100%; margin:0 auto; }
  input { flex:1; background:var(--panel); border:1px solid var(--line);
          border-radius:8px; color:var(--text); padding:10px 12px;
          font-size:15px; }
  input:focus { outline:1px solid var(--accent); }
  button[type=submit] { background:var(--accent); color:#fff; border:0;
      border-radius:8px; padding:0 18px; font-size:15px; cursor:pointer; }
  button:disabled { opacity:.5; cursor:wait; }
  footer { text-align:center; color:var(--dim); font-size:12px;
           padding-bottom:10px; }
</style>
</head>
<body>
<header>
  <h1>🔧 Maintenance Wizard</h1>
  <span>Agentic decision-support for a (synthetic) heavy steel plant</span>
</header>
<div id="log">
  <div class="msg bot">Hello! I'm the Maintenance Wizard. Ask me about any
plant asset — by ID (GEARBOX-05, FURNACE-01, HYD-VALVE-07…) or plain jargon
("the EAF", "that leaking caster valve"). I diagnose with live prognostics,
manuals/SOPs, delay history and spares data, and answer in a five-block
maintenance decision with full traceability.</div>
</div>
<div id="examples">
  <button>What's wrong with the mill gearbox?</button>
  <button>That valve that keeps leaking on the caster</button>
  <button>Status of the charge bay crane</button>
  <button>Check the EAF</button>
</div>
<form id="f">
  <input id="q" autocomplete="off"
         placeholder="Ask about any asset — ID or jargon" />
  <button type="submit" id="send">Send</button>
</form>
<footer>Synthetic data · decision support only · the agent may run several
tool calls per answer (typically 10–30 s)</footer>
<script>
const log = document.getElementById("log");
const form = document.getElementById("f");
const input = document.getElementById("q");
const send = document.getElementById("send");
let history = [];

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",
                                      '"':"&quot;","'":"&#39;"}[m]));
}

// Minimal renderer for the five-block markdown contract: escape first,
// then headers / bold / inline code / blockquotes / line breaks only.
function renderMd(text) {
  return escapeHtml(text)
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function add(cls, text) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  if (cls === "bot") d.innerHTML = renderMd(text);
  else d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function addSources(node, sources) {
  if (!sources || !sources.length) return;
  const seen = new Set();
  const lines = [];
  for (const s of sources) {
    const key = s.source || "?";
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push(key);
  }
  const div = document.createElement("div");
  div.className = "cites";
  div.innerHTML = "<b>Retrieved sources:</b> " +
                  lines.map(escapeHtml).join(" · ");
  node.appendChild(div);
}

async function ask(text) {
  add("user", text);
  input.value = "";
  send.disabled = true;
  const pending = add("bot", "Thinking and running tools…");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({message: text, history}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    history = data.history;
    pending.innerHTML = renderMd(data.text);
    addSources(pending, data.sources);
  } catch (err) {
    pending.textContent = "Error: " + err.message;
    pending.classList.add("err");
  } finally {
    send.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", e => {
  e.preventDefault();
  const text = input.value.trim();
  if (text && !send.disabled) ask(text);
});
document.getElementById("examples").addEventListener("click", e => {
  if (e.target.tagName === "BUTTON" && !send.disabled) ask(e.target.textContent);
});
</script>
</body>
</html>
```

- [ ] **Step 5.2: Commit**

```powershell
git add web/index.html
git commit -m "feat: demo chat UI rendering the five-block contract with retrieved sources"
```

---

## Task 6: Vercel project config

**Files:**
- Create: `web/vercel.json`
- Create: `web/requirements.txt`
- Create: `web/.gitignore`

- [ ] **Step 6.1: Write the config files**

`web/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/chat.py": {
      "maxDuration": 300,
      "includeFiles": "data/**"
    }
  }
}
```

(Hobby-plan duration caps may clamp 300s; the demo's multi-tool turns finish in well under 60s regardless.)

`web/requirements.txt` (slim on purpose — BM25 is stdlib, so one dependency):

```text
google-genai>=1.0
```

`web/.gitignore`:

```gitignore
.vercel/
```

- [ ] **Step 6.2: Commit**

```powershell
git add web/vercel.json web/requirements.txt web/.gitignore
git commit -m "feat: Vercel config for slim Python demo deployment"
```

---

## Task 7: Local end-to-end verification with `vercel dev`

**Files:** none

- [ ] **Step 7.1: Authenticate the Vercel CLI (USER action)**

Run `vercel login` — opens a browser; the user must complete it.

- [ ] **Step 7.2: Run the dev server and smoke-test**

From `web/` (background shell):

```powershell
cd web
$env:GEMINI_API_KEY = (Get-Content ..\.env | Where-Object { $_ -match '^GEMINI_API_KEY=' }) -replace '^GEMINI_API_KEY=',''
vercel dev --listen 3000
```

(First run asks to link/create a project — create new, name `maintenancewiz`, no framework.) Then in another shell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/chat `
  -ContentType "application/json" `
  -Body '{"message":"What''s wrong with the mill gearbox?","history":[]}' |
  Select-Object -ExpandProperty text
```

Expected: a five-block answer for `GEARBOX-05` that mentions the lead-time-exceeds-RUL constraint (the demo centerpiece — the snapshot carries `constraint_flag` for it per `evals/judges.py`). Then open `http://localhost:3000`, click an example chip, and ask a follow-up ("do we have the parts in stock?") to verify multi-turn history survives the round-trip.

Troubleshooting: a `FileNotFoundError` on `data/...` means the `includeFiles` glob didn't apply — move `web/data/` to `web/api/data/`, change `DATA_DIR` in `web/api/_core.py` to `Path(__file__).resolve().parent / "data"`, update `WEB_DATA` in `scripts/build_demo_assets.py`, rerun the export, and re-commit.

---

## Task 8: Publish to GitHub

**Files:** none

- [ ] **Step 8.1: USER CHECKPOINT — confirm publish scope**

Surface to the user before proceeding: (a) the working tree still holds in-flight changes not from this plan (`docs/deck/MaintenanceWizard.pptx`, `knowledge/store/*` — the latter now untracked); (b) publishing merges `codex/hackathon-vercel-demo` → `codex/mw2-port` → `main` and pushes `main` publicly. Get an explicit go-ahead.

- [ ] **Step 8.2: Authenticate gh (USER action)**

`gh auth login` (GitHub.com, HTTPS, browser auth).

- [ ] **Step 8.3: Fast-forward the branch refs and verify**

Do NOT `git checkout codex/mw2-port` / `main` directly: Task 1 untracked `knowledge/store/*` and `ml/artifacts/*.pkl` on this branch, but those paths are still tracked on the older branches and still present on disk, so a plain checkout aborts with "untracked working tree files would be overwritten by checkout". Move the refs instead (no working-tree change):

```powershell
git log codex/mw2-port..main --oneline                        # MUST print nothing (main not diverged)
git log codex/hackathon-vercel-demo..codex/mw2-port --oneline # MUST print nothing (integration branch unchanged since Task 1)
git branch -f codex/mw2-port codex/hackathon-vercel-demo
git branch -f main codex/hackathon-vercel-demo
git switch main          # same commit as the work branch - no tree change, no conflict
python -m evals.judges
python -m evals.demo_tests
```

Expected: both `git log` checks print nothing; both suites pass on `main`. If the FIRST check is non-empty (`main` diverged), STOP and resolve with the user. If the SECOND is non-empty (the in-flight frontend session advanced `codex/mw2-port` — `git branch -f` would silently orphan those commits), STOP: instead merge it into the work branch with `git merge codex/mw2-port`; expect delete/modify conflicts on the untracked artifacts and resolve by keeping the deletion (`git rm -r knowledge/store; git rm ml/artifacts/rul_model.pkl ml/artifacts/fault_model.pkl`), commit, rerun both suites, then redo this step from the top.

- [ ] **Step 8.4: Create the repo and push**

```powershell
gh repo create MaintenanceWiz --public --source=. --remote=origin --push
git push origin codex/mw2-port codex/hackathon-vercel-demo
gh repo view --web
```

Expected: repo visible with `main` as default. Record the URL — the submission's **Repository URL**.

- [ ] **Step 8.5: Final secret sweep of what was published**

```powershell
git ls-files | Select-String -Pattern "\.env$|secret|credential|\.pem|key\.json"
git log --all --oneline -- ".env"
```

Expected: both print nothing. (`web/data/*.json` are demo assets — aliases/tools/snapshot — confirm by eye that no hit is a credential.)

---

## Task 9: Deploy to Vercel production

**Files:** none

- [ ] **Step 9.1: Set production env vars**

From `web/`:

```powershell
vercel env add GEMINI_API_KEY production   # paste the free AI Studio key
vercel env add WIZARD_MODEL production     # enter: gemini-2.5-flash
```

Free-tier limits are project/model/tier dependent — read the live numbers in AI Studio at this point rather than trusting cached figures. If judges exhaust the daily quota, switch `WIZARD_MODEL` to `gemini-2.5-flash-lite` (higher free quota) and redeploy — no code change.

- [ ] **Step 9.2: Deploy**

From `web/`:

```powershell
vercel --prod
```

Expected: a production URL like `https://maintenancewiz.vercel.app`. Record it — the submission's **Demo Link**.

- [ ] **Step 9.3: Production smoke test**

```powershell
Invoke-RestMethod -Method Post -Uri https://<prod-url>/api/chat `
  -ContentType "application/json" `
  -Body '{"message":"Status of the charge bay crane","history":[]}'
```

Expected: JSON whose `text` contains the five blocks and a LOW/MEDIUM priority for `CRANE-06`, plus a `history` array. Then in the browser: run "What's wrong with the mill gearbox?" and confirm the constraint-flag narrative and a Retrieved-sources line; ask a follow-up to confirm multi-turn. A Gemini 429 means free-tier RPM — wait a minute (the UI error message explains).

---

## Task 10: Snapshots (screenshots)

**Files:**
- Create: `docs/submission/snapshots/demo-chat.png`, `docs/submission/snapshots/demo-constraint.png`

- [ ] **Step 10.1: Capture**

Use the Playwright MCP browser (or manual): open the production URL, run "What's wrong with the mill gearbox?", wait for the five-block answer, screenshot the full page → `demo-chat.png`. Capture a close-up of Block 4 (the out-of-stock pinion + constraint flag) and the Retrieved-sources line → `demo-constraint.png`. Each PNG under 3MB.

- [ ] **Step 10.2: Commit**

```powershell
git add docs/submission/snapshots
git commit -m "docs: add demo screenshots for hackathon submission"
git push
```

---

## Task 11: Submission text

**Files:**
- Create: `docs/submission/submission.md`
- Modify: `README.md` (add a short "Hosted demo" section near the top — do NOT touch anything else in it)

- [ ] **Step 11.1: Write the document**

Create `docs/submission/submission.md` (fill the two URLs from Tasks 8/9):

```markdown
# AI Hackathon — Agentic AI Challenge: Submission

## Title
Maintenance Wizard — an Agentic AI Decision-Support Copilot for Heavy Industry

## Theme
Agentic AI

## Demo Link
https://<production-url>.vercel.app

## Repository URL
https://github.com/<user>/MaintenanceWiz

## Description
Unplanned downtime in heavy industry costs millions per day, while the
knowledge needed to prevent it sits scattered across manuals, SOPs, delay
logs, incident records and ERP spares data. Maintenance Wizard is an
**agentic AI maintenance copilot** for a (synthetic) heavy steel plant that
fuses all five sources behind one conversation — and always answers in the
same auditable **five-block decision contract**: risk assessment, root-cause
breakdown, maintenance blueprint, supply-chain strategy, and a traceability
audit trail.

The agent is a single LLM tool-use loop (the "Consolidated Brain" — no
sub-agents) over **twelve tools**: fuzzy asset resolution (plant jargon →
asset ID), RUL prognostics with SHAP attribution, independent abnormality
detection, asset-filtered RAG over manuals/SOPs/incidents, ERP spares
lookup, transparent read-only SQL ("AI to build, UI to validate"), delay
history, deterministic risk scoring, role-routed alert dispatch, work-order
closure compliance, fault-mode classification, and an engineer feedback
loop that re-indexes corrections into retrieval.

What makes it agentic rather than a chatbot: the model decides which tools
to call and in what order, chains evidence across them (sensor deviation →
SHAP driver → SOP procedure → spares lead time), acts on the world
(alerts, closure checks, feedback writes), and obeys an explicit guardrail:
tool outputs are the only source of truth — torque values, part numbers and
isolation steps are never invented. Its signature behavior is
**constraint-aware planning**: when an out-of-stock part's lead time exceeds
the predicted remaining useful life, the recommendation flips from "replace
now" to a monitored-degradation strategy, because the part physically
cannot arrive before failure.

Two builds share the same data and tool contracts: the **full local build**
runs Claude with prompt caching and sentence-level citations, with a fully
deterministic offline fallback (the same tools in pipeline order) that
doubles as the reproducible baseline for the eval judges; the **hosted
demo** is a slim serverless build on Gemini 2.5 Flash (free tier) exposing
10 of the 12 tools over a precomputed prognostics snapshot, BM25 retrieval
and bundled read-only SQLite — so the public link costs nothing to operate.
All demo assets are exported from the real implementation by one script, so
the two builds cannot drift.

All plant data is synthetic. Outputs are decision support requiring
engineer sign-off.

## Instructions to Run

### Hosted demo (no setup)
Open the demo link and ask e.g. "What's wrong with the mill gearbox?" — or
use plant jargon like "check the EAF". The agent runs several tool calls
per answer (typically 10–30 s). Free-tier rate limits apply (the UI
explains retries).

### Full local build
1. `pip install -r requirements.txt`  (the system also runs on
   numpy+pandas+streamlit alone via built-in fallbacks)
2. `python data/generate_mock_data.py`   # synthetic plant data + manuals
3. `python ml/train_model.py`            # RUL model artifact
4. `python knowledge/rag.py`             # RAG index (Chroma or TF-IDF)
5. `streamlit run app/streamlit_app.py`  # 5-panel dashboard
6. Optional: `ANTHROPIC_API_KEY` in `.env` switches the agent from the
   deterministic pipeline to the Claude tool-use loop (same tools, same
   five-block contract).
7. `python -m evals.judges` runs the regression evals;
   `python -m evals.demo_tests` covers the hosted-demo build.
8. Hosted build locally: `cd web && vercel dev` with `GEMINI_API_KEY` set.

## Video URL (optional)
90-second walkthrough script:
1. (0:00) Problem: one sentence over the architecture slide.
2. (0:10) Open the demo, click "What's wrong with the mill gearbox?".
3. (0:25) While it thinks, narrate the tools it is calling.
4. (0:40) Show the five-block answer; zoom on the constraint flag — the
   pinion's 45-day lead time exceeds the predicted RUL, so the agent
   switches to monitored degradation instead of "replace now".
5. (1:00) Follow-up: "that valve that keeps leaking on the caster" —
   jargon-to-asset resolution.
6. (1:15) Mention the full Claude build: citations + deterministic
   offline fallback + eval judges.
7. (1:25) Close: synthetic-data caveat + repo link.
```

- [ ] **Step 11.2: Add the README hosted-demo section**

Insert near the top of `README.md` (after the title/intro, before setup):

```markdown
## Hosted demo

Live demo (slim serverless build, Gemini 2.5 Flash free tier):
**https://<production-url>.vercel.app** — see `web/`. It exposes 10 of the
12 tools over a precomputed prognostics snapshot, BM25 retrieval and
bundled read-only SQLite, all exported from the real implementation by
`scripts/build_demo_assets.py`. The full build (Claude tool-use loop +
deterministic fallback) runs locally per the instructions below.
```

- [ ] **Step 11.3: Commit**

```powershell
git add docs/submission/submission.md README.md
git commit -m "docs: hackathon submission text, run instructions, demo link"
git push
```

---

## Task 12: Pitch deck — verify the existing one

**Files:** none created — `docs/deck/MaintenanceWizard.pptx` already exists (with PDF and `build_deck.js`), and has uncommitted in-flight edits owned by another session.

- [ ] **Step 12.1: Verify and hand off**

```powershell
(Get-Item docs\deck\MaintenanceWizard.pptx).Length / 1MB
```

Expected: well under 50MB (portal limit). Tell the user: the deck is the submission's Presentation asset; if they want the demo/repo URLs added to a slide, that edit belongs to the in-flight deck session — do not modify the pptx from this plan.

---

## Task 13: Source zip

**Files:**
- Create: `dist/MaintenanceWiz-source.zip` (NOT committed — `dist/` was gitignored in Task 1)

- [ ] **Step 13.1: Build from tracked files only**

```powershell
New-Item -ItemType Directory -Force dist | Out-Null
git archive --format=zip -o dist/MaintenanceWiz-source.zip HEAD
(Get-Item dist\MaintenanceWiz-source.zip).Length / 1MB
```

Expected: a few MB, well under 50MB. `git archive` guarantees only committed files — no `.env`, no store binaries, no model pkl.

- [ ] **Step 13.2: Verify the zip contents**

```powershell
python -c "import zipfile; names = zipfile.ZipFile('dist/MaintenanceWiz-source.zip').namelist(); bad = [n for n in names if '.env' in n or 'secret' in n.lower()]; print('BAD:', bad) if bad else print(f'OK: {len(names)} files, no secrets')"
```

Expected: `OK: <N> files, no secrets`.

---

## Task 14: Final submission checklist

**Files:** none

- [ ] **Step 14.1: Walk the portal checklist with the user**

| Field | Status / source |
|---|---|
| Title* | from `docs/submission/submission.md` |
| Description* | from `docs/submission/submission.md` |
| Theme* | Agentic AI (select in portal) |
| Presentation* | `docs/deck/MaintenanceWizard.pptx` (existing; <50MB verified in Task 12) |
| Demo Link* | production vercel.app URL (smoke-tested in Task 9) |
| Source Code* | `dist/MaintenanceWiz-source.zip` (<50MB, secret-free) |
| Snapshots | 2 PNGs in `docs/submission/snapshots/` (<3MB each) |
| Video URL | optional — user records with the script in submission.md |
| Repository URL | GitHub URL from Task 8 |
| Instructions to Run | from `docs/submission/submission.md` |

- [ ] **Step 14.2: Final sanity pass**

Re-open the production demo in a fresh browser, run one full example end-to-end (gearbox → constraint flag → sources), confirm the GitHub README renders with the hosted-demo section, then run the full local guard one last time:

```powershell
python -m evals.judges
python -m evals.demo_tests
```

Report all URLs and file paths to the user for upload.
