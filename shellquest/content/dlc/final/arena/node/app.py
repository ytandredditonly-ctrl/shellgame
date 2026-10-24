#!/usr/bin/env python3
"""DLC finale arena 'proving-ground' web tier. Exposes a dumpable credential
and an admin area, chaining recon -> web -> password -> capture. Local only.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
class H(BaseHTTPRequestHandler):
    server_version = "proving/1.0"
    def _s(self, code, body, ctype="text/html"):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path.rstrip("/") or "/"
        if p == "/":
            self._s(200, "proving-ground — /login, /admin\n")
        elif p == "/robots.txt":
            self._s(200, "User-agent: *\nDisallow: /admin\n", "text/plain")
        elif p == "/admin":
            # leaks a credential + a crackable md5 (provingpass)
            self._s(200, "admin:provingpass\nhash:7e9e1a... (md5 of provingpass)\n", "text/plain")
        elif p == "/login":
            self._s(200, "login form\n")
        else:
            self._s(404, "not found\n")
    def log_message(self, *a): pass
HTTPServer(("0.0.0.0", 80), H).serve_forever()
