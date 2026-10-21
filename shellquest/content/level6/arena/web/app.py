#!/usr/bin/env python3
"""web host for the level-6 recon arena: nginx-fingerprinted, hidden /backup,
plus a non-standard port (8443). Training arena only."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    # Override the auto-emitted Server header so fingerprinting reads "nginx".
    server_version = "nginx/1.24.0"
    sys_version = ""

    def _s(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path.rstrip("/") == "/backup":
            self._s(200, b"<h1>backup index</h1>")
        elif self.path == "/":
            self._s(200, b"<html><body><h1>web</h1></body></html>")
        else:
            self._s(404, b"not found")
    def log_message(self, *a): pass

def serve(port):
    HTTPServer(("0.0.0.0", port), H).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=serve, args=(8443,), daemon=True).start()
    serve(80)
