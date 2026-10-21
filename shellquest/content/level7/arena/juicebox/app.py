#!/usr/bin/env python3
"""juicebox — a deliberately vulnerable training web app (level 7).

Teaches: SQL injection auth bypass, hidden parameters, and finding flags in an
admin area. Runs ONLY inside the isolated arena network. Vulnerabilities are
intentional and must never be exposed outside the lab.
"""
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

AUTH_BYPASS_FLAG = "WEB-AUTH-BYPASS-11"
WEAVER_FLAG = "WEAVER-CORE-88"


def db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE users (id INTEGER, username TEXT, password TEXT, role TEXT)")
    c.execute("INSERT INTO users VALUES (1,'admin','5f4dcc3b5aa765d61d8327deb882cf99','admin')")
    c.execute("INSERT INTO users VALUES (2,'alice','e10adc3949ba59abbe56e057f20f883e','user')")
    return c


LOGIN = """<html><body><h1>juicebox</h1>
<form method="POST" action="/login">
 <input name="username" placeholder="user">
 <input name="password" type="password" placeholder="password">
 <button>Sign in</button>
</form></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Server", "nginx")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/login"):
            self._send(200, LOGIN)
        elif u.path == "/search":
            q = parse_qs(u.query)
            # Hidden parameter: `debug` reveals internals (level 7 q04).
            if "debug" in q:
                self._send(200, "<pre>debug: routes=/,/login,/search,/profile,/admin</pre>")
            else:
                self._send(200, "<p>search results: none</p>")
        elif u.path == "/admin":
            self._send(200, f"<h1>admin</h1><p>flag: {WEAVER_FLAG}</p>")
        elif u.path == "/profile":
            self._send(200, f"<h1>profile</h1><p>flag: {AUTH_BYPASS_FLAG}</p>")
        else:
            self._send(404, "<p>not found</p>")

    def do_POST(self):
        if urlparse(self.path).path != "/login":
            return self._send(404, "nope")
        n = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(n).decode())
        user = form.get("username", [""])[0]
        pw = form.get("password", [""])[0]
        # VULNERABLE on purpose: string-built SQL -> classic ' OR '1'='1 bypass.
        sql = ("SELECT role FROM users WHERE username='%s' AND password='%s'"
               % (user, pw))
        try:
            row = db().execute(sql).fetchone()
        except sqlite3.Error as e:
            return self._send(200, f"<pre>sql error: {e}</pre>")
        if row:
            self._send(200, f'<p>welcome, role={row[0]}</p>'
                            f'<a href="/profile">profile</a>')
        else:
            self._send(200, "<p>invalid credentials</p>")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 80), H).serve_forever()
