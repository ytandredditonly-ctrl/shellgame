#!/usr/bin/env python3
"""db host: emits an outdated-service version banner on connect so `nmap -sV`
fingerprints it (level-6 q03). Training arena only."""
import socket
BANNER = b"PostgreSQL 9.3.0 (outdated) ready\n"
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 5432)); s.listen(16)
while True:
    try:
        c, _ = s.accept()
        c.sendall(BANNER)
        c.close()
    except Exception:
        pass
