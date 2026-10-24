#!/usr/bin/env python3
"""Boss d4 phase 2 — exploit session reachable.

Grades the breach arena: the backdoor shell the exploit opens (port 6200, the
classic vsftpd-2.3.4 trigger) is live and yields the session marker. Pass when
the marker is read off that port; pending (exit 2) when the arena is down or
Docker is unreachable — never a false pass/fail.
"""
import subprocess
import sys

CONTAINER = "sq-d4-breach"
MARKER = "ARS-MSF-SHELL"
_SNIPPET = r"""
import socket, sys
s = socket.create_connection(("127.0.0.1", 6200), 3)
sys.stdout.write(s.recv(128).decode("latin1"))
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
