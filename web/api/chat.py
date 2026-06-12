"""Vercel Python function for the hosted demo.

The pyproject [tool.vercel] entrypoint routes ALL requests here (the current
Python runtime does not serve static files alongside an entrypoint), so this
handler serves the chat UI on GET / and the wizard API on POST /api/chat:
{message, history} -> {text, sources, stop_reason, history}.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._core import chat_turn, rate_limited  # noqa: E402

INDEX_HTML = Path(__file__).resolve().parent.parent / "index.html"
MAX_HISTORY_MESSAGES = 60  # ~10 multi-tool turns; caps token spend


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = INDEX_HTML.read_bytes()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(404, {"error": "not found"})

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
