#!/usr/bin/env python3
"""DLC d6 arena 'loginbox' HTTP tier: a weak login form with a simple
rate-limit (HTTP 429 after 5 tries per client). admin/letmein unlocks the flag.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
tries = {}
class H(BaseHTTPRequestHandler):
    server_version = "loginbox/1.0"
    def _s(self, code, body):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        ip = self.client_address[0]
        tries[ip] = tries.get(ip, 0) + 1
        if tries[ip] > 5:
            self._s(429, "429 Too Many Requests\n"); return
        n = int(self.headers.get("Content-Length", 0) or 0)
        d = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        user = d.get("user", [""])[0]; pw = d.get("pass", [""])[0]
        if user == "admin" and pw == "letmein":
            self._s(200, "OK flag ARS-HYDRA-IN\n")
        else:
            self._s(200, "FAIL\n")
    def do_GET(self):
        self._s(200, "POST user=&pass= to /login\n")
    def log_message(self, *a): pass
HTTPServer(("0.0.0.0", 8080), H).serve_forever()
