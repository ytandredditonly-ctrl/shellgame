#!/usr/bin/env python3
"""DLC d10 arena 'serverbox' — generates deterministic local HTTP traffic
carrying a token and the module flag, to be captured with tcpdump. Loopback
only; internal:true network, no outbound.
"""
import socket, threading, time
TOKEN = "ARSENAL-TCPD-55"; FLAG = "ARS-TCPD-CATCH"
def server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80)); s.listen(16)
    while True:
        try: c, _ = s.accept()
        except OSError: continue
        try:
            c.recv(1024)
            body = f"status ok token={TOKEN} flag={FLAG}\n"
            c.sendall(("HTTP/1.1 200 OK\r\nX-Token: %s\r\nContent-Length: %d\r\n\r\n%s"
                       % (TOKEN, len(body), body)).encode())
        except OSError: pass
        finally: c.close()
threading.Thread(target=server, daemon=True).start()
time.sleep(1)
while True:
    try:
        c = socket.create_connection(("127.0.0.1", 80), 3)
        c.sendall(b"GET /status HTTP/1.1\r\nHost: serverbox\r\nX-Token: %s\r\n\r\n" % TOKEN.encode())
        c.recv(512); c.close()
    except OSError: pass
    time.sleep(1)
