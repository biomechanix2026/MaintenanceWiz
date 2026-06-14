"""Read-only dashboard payload for the hosted Vercel demo."""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._core import dashboard_payload  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self._send(200, dashboard_payload())
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
