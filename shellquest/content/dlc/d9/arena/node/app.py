#!/usr/bin/env python3
"""DLC d9 arena 'webmaze' — hidden paths, a forgotten .bak, and a secret GET
parameter, for nikto / gobuster / ffuf practice. Local/internal only.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

FLAG = "ARS-RECON-HIDDEN"
ROBOTS = "User-agent: *\nDisallow: /backup\nDisallow: /admin/panel\n"

class H(BaseHTTPRequestHandler):
    server_version = "ArsenalCMS/1.0"
    def _send(self, code, body, ctype="text/html"):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        p = u.path.rstrip("/") or "/"
        if p == "/":
            self._send(200, "ArsenalCMS home\n")
        elif p == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
        elif p == "/admin":
            self._send(200, "admin login\n")
        elif p == "/backup":
            self._send(200, "index of /backup\nsecret.bak\n")
        elif p == "/secret.bak":
            self._send(200, "DEV_NOTE backup-key-7781\n", "text/plain")
        elif p == "/p":
            if q.get("debug", [""])[0]:
                self._send(200, "debug mode on\n")
            else:
                self._send(200, "normal view\n")
        elif p == "/admin/panel":
            if q.get("debug", [""])[0] == "1":
                self._send(200, f"RECON-OK {FLAG}\n", "text/plain")
            else:
                self._send(403, "need debug param\n")
        else:
            self._send(404, "not found\n")
    def log_message(self, *a): pass

HTTPServer(("0.0.0.0", 80), H).serve_forever()
