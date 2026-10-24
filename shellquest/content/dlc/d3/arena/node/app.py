#!/usr/bin/env python3
"""DLC d3 arena 'shopfront' — a deliberately weak web app for Burp practice.
Trusts client-supplied cookie 'role' and a client 'qty'. Local/internal only.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

FLAG = "ARS-BURP-TAMPER"

class H(BaseHTTPRequestHandler):
    server_version = "shopfront/1.0"
    def _role(self):
        c = self.headers.get("Cookie", "")
        for kv in c.split(";"):
            if kv.strip().startswith("role="):
                return kv.strip()[5:]
        return "guest"
    def _send(self, code, body, ctype="text/plain", cookie=None):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/":
            role = self._role()
            msg = "WELCOME_ADMIN" if role == "admin" else "welcome, guest"
            self._send(200, f"shopfront store\n{msg}\n", cookie="role=guest")
        elif u.path == "/admin":
            if self._role() == "admin":
                self._send(200, f"admin panel\nflag {FLAG}\n")
            else:
                self._send(403, "forbidden role=guest\n")
        elif u.path == "/deals":
            if q.get("code", [""])[0] == "ARSENAL50":
                self._send(200, "DEAL UNLOCKED: hidden section open\n")
            else:
                self._send(200, "enter coupon code\n")
        else:
            self._send(404, "not found\n")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        if urlparse(self.path).path == "/cart":
            qty = int((data.get("qty", ["1"])[0] or "1"))
            if qty > 10:
                self._send(200, "OUT_OF_STOCK\n")
            else:
                self._send(200, f"OK qty={qty}\n")
        else:
            self._send(404, "not found\n")
    def log_message(self, *a): pass

HTTPServer(("0.0.0.0", 80), H).serve_forever()
