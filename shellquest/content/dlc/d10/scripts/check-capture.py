#!/usr/bin/env python3
"""Boss d10 phase 1 — the cleartext token is on the wire.

Grades the serverbox arena: the service emits the secret token/flag in its
payload (what the player captures with tcpdump over SSH). Pass when the arena
serves the marker; pending (exit 2) when the arena is down or Docker is
unreachable — never a false pass/fail.
"""
import subprocess
import sys

CONTAINER = "sq-d10-serverbox"
MARKER = "ARS-TCPD-CATCH"
_SNIPPET = r"""
import socket, sys
s = socket.create_connection(("127.0.0.1", 80), 3)
s.sendall(b"GET /status HTTP/1.0\r\nHost: serverbox\r\n\r\n")
buf = b""
while True:
    d = s.recv(4096)
    if not d:
        break
    buf += d
sys.stdout.write(buf.decode("latin1"))
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
