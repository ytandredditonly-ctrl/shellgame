#!/usr/bin/env python3
"""Boss d3 phase 1 — Burp tamper path is live.

Grades the shopfront arena: a request carrying the tampered `role=admin` cookie
reaches the admin area (the exact client-trust flaw the player exploits through
Burp). Pass when the arena returns the admin marker; pending (exit 2) when the
arena is down or Docker is unreachable — never a false pass/fail.
"""
import subprocess
import sys

CONTAINER = "sq-d3-shopfront"
MARKER = "ARS-BURP-TAMPER"
_SNIPPET = r"""
import socket
s = socket.create_connection(("127.0.0.1", 80), 3)
s.sendall(b"GET /admin HTTP/1.0\r\nCookie: role=admin\r\n\r\n")
buf = b""
while True:
    d = s.recv(4096)
    if not d:
        break
    buf += d
import sys; sys.stdout.write(buf.decode("latin1"))
"""


def main() -> int:
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "python3", "-c", _SNIPPET],
            capture_output=True, text=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return 2
    return 0 if r.returncode == 0 and MARKER in r.stdout else 2


if __name__ == "__main__":
    sys.exit(main())
