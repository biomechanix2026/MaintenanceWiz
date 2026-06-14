"""Regression tests for Vercel Git builds from the repository root.

Run:  python -m evals.vercel_root_tests
"""
from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def test_root_pyproject_points_vercel_git_build_to_web_entrypoint():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["vercel"]["entrypoint"] == "web.api.chat:handler"


def test_chat_entrypoint_serves_dashboard_for_root_vercel_builds():
    chat = importlib.import_module("web.api.chat")
    request = object.__new__(chat.handler)
    request.path = "/api/dashboard"
    captured = {}

    def fake_send(code, payload):
        captured["code"] = code
        captured["payload"] = payload

    request._send = fake_send
    request.do_GET()
    assert captured["code"] == 200
    assert captured["payload"]["asset_count"] == 12
    assert captured["payload"]["signature_story"]["asset_id"] == "GEARBOX-05"


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as e:
            failures.append((name, e))
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
