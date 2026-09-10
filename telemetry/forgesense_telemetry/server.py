from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import TelemetryStore


class TelemetryHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, store: TelemetryStore, dashboard_dir: Path):
        self.store = store
        self.dashboard_dir = dashboard_dir.resolve()
        super().__init__(server_address, TelemetryHandler)


class TelemetryHandler(BaseHTTPRequestHandler):
    server: TelemetryHttpServer

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, relative: str) -> None:
        target = (self.server.dashboard_dir / relative).resolve()
        if self.server.dashboard_dir not in target.parents and target != self.server.dashboard_dir:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        suffix = target.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/health":
            snapshot = self.server.store.snapshot()
            self._json({
                "ok": True,
                "schema": snapshot["schema"],
                "revision": snapshot["revision"],
                "status_fresh": snapshot["system"]["status_fresh"],
            })
            return
        if parsed.path == "/api/v1/snapshot":
            self._json(self.server.store.snapshot())
            return
        if parsed.path == "/api/v1/events":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                events = self.server.store.events(limit=limit)
            except (ValueError, TypeError):
                self._json({"error": "invalid limit"}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"events": events})
            return
        if parsed.path == "/api/v1/stream":
            query = parse_qs(parsed.query)
            try:
                after = int(query.get("after", ["-1"])[0])
            except ValueError:
                self._json({"error": "invalid revision"}, HTTPStatus.BAD_REQUEST)
                return
            self.server.store.wait_for_revision(after, timeout_s=15.0)
            self._json(self.server.store.snapshot())
            return
        if parsed.path in ("/", "/index.html"):
            self._static("index.html")
            return
        if parsed.path == "/app.js":
            self._static("app.js")
            return
        if parsed.path == "/styles.css":
            self._static("styles.css")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        self._json(
            {"error": "read-only monitoring API; control operations are not exposed"},
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
