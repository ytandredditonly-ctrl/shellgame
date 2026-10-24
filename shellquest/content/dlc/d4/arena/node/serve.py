#!/usr/bin/env python3
"""recon-net training node (DLC d1). Opens a set of TCP listeners described by
the SQ_PORTS env var so nmap sees deterministic ports/services/versions.

SQ_PORTS = comma-separated "PORT=KIND[:arg[:arg]]" entries:
    ssh                      -> SSH-2.0 banner
    http:<server>:<title>    -> HTTP 200 with Server header + <title>
    ftp                      -> vsFTPd 220 banner
    mysql                    -> short MySQL greeting
    flag:<value>             -> emits a beacon string (the boss flag)
    tcp:<banner>             -> raw banner

Training only — bound inside an internal:true Docker network, no outbound.
"""
import os
import socket
import threading


def handle(kind: str, args: list[str], conn: socket.socket) -> None:
    try:
        if kind == "http":
            server = args[0] if args else "nginx/1.18.0"
            title = args[1] if len(args) > 1 else "Node"
            try:
                conn.recv(1024)
            except OSError:
                pass
            body = f"<html><head><title>{title}</title></head><body>ok</body></html>"
            resp = (
                "HTTP/1.1 200 OK\r\n"
                f"Server: {server}\r\n"
                "Content-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n" + body
            )
            conn.sendall(resp.encode())
        elif kind == "ssh":
            conn.sendall(b"SSH-2.0-OpenSSH_8.4p1 Debian-5\r\n")
        elif kind == "ftp":
            conn.sendall(b"220 (vsFTPd 3.0.3)\r\n")
        elif kind == "mysql":
            conn.sendall(b"J\x00\x00\x00\x0a8.0.32\x00")
        elif kind == "flag":
            value = args[0] if args else "ARS-NMAP-MAP"
            conn.sendall(f"RECON-BEACON {value}\r\n".encode())
        else:  # tcp / unknown
            conn.sendall(((args[0] if args else "service") + "\r\n").encode())
    except OSError:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def listen(port: int, kind: str, args: list[str]) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(16)
    while True:
        try:
            conn, _ = s.accept()
        except OSError:
            continue
        threading.Thread(target=handle, args=(kind, args, conn), daemon=True).start()


def main() -> None:
    spec = os.environ.get("SQ_PORTS", "")
    threads = []
    for entry in filter(None, (e.strip() for e in spec.split(","))):
        port_s, _, rest = entry.partition("=")
        parts = rest.split(":")
        kind = parts[0] if parts and parts[0] else "tcp"
        args = parts[1:]
        try:
            port = int(port_s)
        except ValueError:
            continue
        t = threading.Thread(target=listen, args=(port, kind, args), daemon=True)
        t.start()
        threads.append(t)
    if not threads:
        return
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
