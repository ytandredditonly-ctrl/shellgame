"""`sq gui` — the read-only companion window (GUI spec).

A tiny local web server (stdlib only) serves a dark single-page app on
127.0.0.1 and pushes live state over Server-Sent Events. The page renders the
snapshot from `sq.snapshot`; it never mutates game state — buttons copy `sq ...`
commands to the clipboard for the terminal (GUI spec §9).

Routes:
  GET /                 the SPA
  GET /api/state        one state snapshot (JSON)
  GET /api/stream       SSE; pushes the snapshot whenever state_version changes
  GET /api/codex?tool=  a codex card (markdown) for one tool
  GET /api/manual       commands table + how-to (JSON)
"""
from __future__ import annotations

import json
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import content as C
from . import snapshot
from .db import DB

WEBUI = Path(__file__).resolve().parent / "webui"
_CONTENT: C.Content | None = None


def _content() -> C.Content:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = C.Content()
    return _CONTENT


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._serve_file("index.html", "text/html; charset=utf-8")
            elif u.path == "/app.js":
                self._serve_file("app.js", "application/javascript; charset=utf-8")
            elif u.path == "/app.css":
                self._serve_file("app.css", "text/css; charset=utf-8")
            elif u.path == "/api/state":
                with _db() as db:
                    self._json(snapshot.build(db, _content()))
            elif u.path == "/api/manual":
                self._json({"commands": snapshot.COMMANDS_TABLE, "howto": snapshot.HOWTO})
            elif u.path == "/api/codex":
                tool = parse_qs(u.query).get("tool", [""])[0]
                card = snapshot.codex_card(_content(), tool)
                self._json({"tool": tool, "card": card})
            elif u.path == "/api/stream":
                self._stream()
            else:
                self._send(404, b"not found")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # never 500 the GUI into a stack trace
            try:
                self._json({"error": str(e)}, 500)
            except Exception:
                pass

    def _serve_file(self, name, ctype):
        f = WEBUI / name
        if not f.is_file():
            self._send(404, b"missing asset")
            return
        self._send(200, f.read_bytes(), ctype)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_ver = None
        last_beat = 0.0
        while True:
            try:
                with _db() as db:
                    ver = snapshot.state_version(db)
                    if ver != last_ver:
                        last_ver = ver
                        snap = snapshot.build(db, _content())
                        payload = json.dumps(snap, ensure_ascii=False)
                        self.wfile.write(f"event: state\ndata: {payload}\n\n".encode())
                        self.wfile.flush()
                now = time.time()
                if now - last_beat > 15:
                    last_beat = now
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                break

    def log_message(self, *a):
        pass


class _db:
    def __enter__(self):
        self.db = DB()
        return self.db
    def __exit__(self, *a):
        self.db.close()


def run(port: int = 8777, open_browser: bool = True) -> int:
    if not (WEBUI / "index.html").is_file():
        print("GUI assets missing:", WEBUI, file=sys.stderr)
        return 1
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    url = f"http://127.0.0.1:{port}/"
    print(f"shellquest GUI on {url}  (Ctrl+C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.port, not a.no_browser))
