#!/usr/bin/env python3
"""Tiny HTTP server for the gatekeeper arena: serves the welcome page."""
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = b"<html><body><h1>welcome</h1><p>gatekeeper online</p></body></html>"

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE)
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), H).serve_forever()
