#!/usr/bin/env python3
"""DLC d7 arena 'dbshop' — a web app with a classic SQL injection in ?id=.
Back-end: SQLite. String-concatenated query (intentionally vulnerable). Local only.
"""
import socket, sqlite3, threading
from urllib.parse import urlparse, parse_qs

db = sqlite3.connect(":memory:", check_same_thread=False)
db.executescript("""
CREATE TABLE products(id INTEGER, name TEXT, price TEXT);
INSERT INTO products VALUES(1,'Lockpick','9.99'),(2,'Proxy','19.99');
CREATE TABLE users(id INTEGER, username TEXT, password TEXT, role TEXT);
INSERT INTO users VALUES(1,'admin','5f4dcc3b5aa765d61d8327deb882cf99','admin'),
                        (2,'bob','e10adc3949ba59abbe56e057f20f883e','user');
CREATE TABLE vault(id INTEGER, secret TEXT);
INSERT INTO vault VALUES(1,'ARS-SQLI-DUMP');
""")
lock = threading.Lock()

def page(qs):
    idv = parse_qs(qs).get("id", ["1"])[0]
    sql = "SELECT name, price FROM products WHERE id=" + idv  # VULNERABLE
    try:
        with lock:
            rows = db.execute(sql).fetchall()
        body = "".join(f"{r[0]} :: {r[1]}\n" for r in rows) or "no rows\n"
        return 200, body
    except Exception as e:  # error-based: leak the SQLite message
        return 500, f"SQL error: {e}\n"

def handle(c):
    try:
        req = c.recv(4096).decode("latin1")
        line = req.split("\r\n", 1)[0]
        path = line.split(" ")[1] if len(line.split(" ")) > 1 else "/"
        u = urlparse(path)
        if u.path == "/item":
            code, body = page(u.query)
        elif u.path == "/":
            code, body = 200, "dbshop — try /item?id=1\n"
        else:
            code, body = 404, "not found\n"
        c.sendall(("HTTP/1.1 %d OK\r\nServer: dbshop/1.0\r\nContent-Type: text/html\r\n"
                   "Content-Length: %d\r\nConnection: close\r\n\r\n%s"
                   % (code, len(body.encode()), body)).encode())
    except OSError:
        pass
    finally:
        try: c.close()
        except OSError: pass

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 80)); s.listen(32)
while True:
    try:
        conn, _ = s.accept()
    except OSError:
        continue
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
