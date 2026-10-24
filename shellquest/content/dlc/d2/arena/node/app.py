#!/usr/bin/env python3
"""DLC d2 arena node 'chatter': emits deterministic local traffic carrying a
training token so a live capture (tshark/Wireshark) can find it. Loopback only;
the container sits on an internal:true network with no outbound.
"""
import socket, threading, time

TOKEN = "CHATTER-FEED-42"

def server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 8080)); s.listen(16)
    while True:
        try:
            c, _ = s.accept()
        except OSError:
            continue
        try:
            c.recv(1024)
            body = f"feed token={TOKEN}\n"
            c.sendall(("HTTP/1.1 200 OK\r\nX-Feed: %s\r\nContent-Length: %d\r\n\r\n%s"
                       % (TOKEN, len(body), body)).encode())
        except OSError:
            pass
        finally:
            c.close()

threading.Thread(target=server, daemon=True).start()
time.sleep(1)
while True:
    try:
        c = socket.create_connection(("127.0.0.1", 8080), 3)
        c.sendall(b"GET /feed HTTP/1.1\r\nHost: chatter\r\nX-Feed: %s\r\n\r\n" % TOKEN.encode())
        c.recv(512); c.close()
    except OSError:
        pass
    time.sleep(2)
