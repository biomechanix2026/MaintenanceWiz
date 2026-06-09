"""
Tiny zero-dependency test harness for the requirement-conformance suites.

Mirrors the style of `evals/judges.py` (runnable as `python -m evals.<module>`),
so the project keeps its no-pytest, numpy+pandas-only footprint. Each suite
collects `@suite.case` functions, runs them, and prints PASS / FAIL / GAP.

A `GAP` is a *known, documented* shortfall (e.g. role-based alerts) raised via
`gap("reason")`; it is reported but does not fail the suite, matching the test
design's instruction to track such items as checklist/expected items.
"""
from __future__ import annotations
import os
import sys
import shutil
import tempfile
import contextlib

# UTF-8 stdout so PASS/FAIL glyphs don't crash the default Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


class KnownGap(Exception):
    """Raised by a case to mark a documented, expected shortfall."""


def gap(reason: str):
    raise KnownGap(reason)


def approx(value, lo, hi):
    assert lo <= value <= hi, f"{value} not in [{lo}, {hi}]"


class Suite:
    def __init__(self, name: str):
        self.name = name
        self.cases = []

    def case(self, fn):
        self.cases.append(fn)
        return fn

    def run(self) -> tuple[int, int, int, list]:
        passed = failed = gaps = 0
        results = []
        for fn in self.cases:
            rid = fn.__name__.replace("test_", "").replace("_", "-").upper()
            try:
                fn()
                results.append((rid, "PASS", "")); passed += 1
            except KnownGap as e:
                results.append((rid, "GAP", str(e))); gaps += 1
            except AssertionError as e:
                results.append((rid, "FAIL", str(e) or "assertion failed")); failed += 1
            except Exception as e:
                results.append((rid, "FAIL", f"{type(e).__name__}: {e}")); failed += 1
        return passed, failed, gaps, results


def run_suites(*suites: Suite) -> int:
    total_p = total_f = total_g = 0
    print("=" * 70)
    for s in suites:
        p, f, g, results = s.run()
        total_p += p; total_f += f; total_g += g
        print(f"\n[{s.name}]  {p} pass / {f} fail / {g} gap")
        for rid, status, msg in results:
            mark = {"PASS": "✓", "FAIL": "✗", "GAP": "▲"}[status]
            line = f"   {mark} {rid:<10} {status}"
            if msg:
                line += f"  — {msg}"
            print(line)
    print("\n" + "-" * 70)
    print(f"TOTAL: {total_p} passed, {total_f} failed, {total_g} known-gaps")
    return 0 if total_f == 0 else 1


@contextlib.contextmanager
def sandbox():
    """Redirect all writeable paths (feedback, logbook, notifications, RAG index)
    to a temp dir so write-path tests never touch repo data. Real read-only
    artifacts (registry, sensors, manuals, incidents, parts) are untouched.

    Patches BOTH `config` (read at call-time by agent.tools) AND
    `knowledge.rag` (which binds some path names at import-time), then resets the
    lazy singletons so the next call reloads against the sandbox.
    """
    import config as C
    import agent.tools as T
    import knowledge.rag as R

    d = tempfile.mkdtemp(prefix="mw_test_")
    saved_c = {k: getattr(C, k) for k in ("FEEDBACK_CSV", "LOGBOOK_CSV", "DATA_DIR", "VECTORSTORE_DIR")}
    saved_r = {k: getattr(R, k) for k in ("FEEDBACK_CSV", "VECTORSTORE_DIR", "_TFIDF_PATH")}
    saved_rag, saved_db = T._RAG, T._DB
    store = os.path.join(d, "store")
    os.makedirs(store, exist_ok=True)
    try:
        C.FEEDBACK_CSV = os.path.join(d, "feedback.csv")
        C.LOGBOOK_CSV = os.path.join(d, "digital_logbook.csv")
        C.DATA_DIR = d
        C.VECTORSTORE_DIR = store
        R.FEEDBACK_CSV = C.FEEDBACK_CSV
        R.VECTORSTORE_DIR = store
        R._TFIDF_PATH = os.path.join(store, "tfidf_index.pkl")
        T._RAG = None
        T._DB = None
        yield d
    finally:
        for k, v in saved_c.items():
            setattr(C, k, v)
        for k, v in saved_r.items():
            setattr(R, k, v)
        T._RAG, T._DB = saved_rag, saved_db
        shutil.rmtree(d, ignore_errors=True)
