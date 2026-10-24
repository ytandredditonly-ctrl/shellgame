#!/usr/bin/env python3
"""Generate a deterministic training capture sample.pcap for DLC d2.

14 packets, all synthetic and local (10.13.0.0/24). Readable by tshark/Wireshark:
  - DNS query/response for shop.lab.local        (q02 answer: shop.lab.local)
  - HTTP GET /login                               (q03 answer: /login)
  - HTTP POST /auth with body pwd=hunter2         (q04 answer: hunter2)
  - HTTP 200 whose body carries the module flag   (boss p3: ARS-WIRE-DECODE)
  - 3x TLS ClientHello, SNI vault.lab.local       (boss p1: 3, p2: vault.lab.local)
Total packets = 14 (boss/quest q01 answer).
"""
import struct, sys, os

OUT = sys.argv[1] if len(sys.argv) > 1 else "sample.pcap"

def ipv4_cksum(h):
    s = 0
    for i in range(0, len(h), 2):
        s += (h[i] << 8) + h[i+1]
    s = (s >> 16) + (s & 0xffff); s += (s >> 16)
    return (~s) & 0xffff

def eth(src, dst, etype=0x0800):
    return dst + src + struct.pack("!H", etype)

MAC_A = bytes.fromhex("020000000001")
MAC_B = bytes.fromhex("020000000002")
IP_A = bytes([10,13,0,10]); IP_B = bytes([10,13,0,20]); IP_DNS = bytes([10,13,0,53])

def ip(src, dst, proto, payload, ident):
    ver_ihl = 0x45; tos = 0; total = 20 + len(payload)
    hdr = struct.pack("!BBHHHBBH", ver_ihl, tos, total, ident, 0x4000, 64, proto, 0) + src + dst
    ck = ipv4_cksum(hdr)
    hdr = hdr[:10] + struct.pack("!H", ck) + hdr[12:]
    return hdr + payload

def udp(sport, dport, payload):
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload

def tcp(sport, dport, seq, ack, flags, payload=b""):
    off = (5 << 4)
    return struct.pack("!HHIIBBHHH", sport, dport, seq, ack, off, flags, 65535, 0, 0) + payload

def dns_name(n):
    out = b""
    for lab in n.split("."):
        out += bytes([len(lab)]) + lab.encode()
    return out + b"\x00"

def dns_query(name, ident):
    return struct.pack("!HHHHHH", ident, 0x0100, 1, 0, 0, 0) + dns_name(name) + struct.pack("!HH", 1, 1)

def dns_resp(name, ip_bytes, ident):
    q = dns_name(name) + struct.pack("!HH", 1, 1)
    ans = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + ip_bytes
    return struct.pack("!HHHHHH", ident, 0x8180, 1, 1, 0, 0) + q + ans

def tls_client_hello(sni):
    server_name = sni.encode()
    sni_list = struct.pack("!B", 0) + struct.pack("!H", len(server_name)) + server_name
    sni_ext_data = struct.pack("!H", len(sni_list)) + sni_list
    ext = struct.pack("!HH", 0x0000, len(sni_ext_data)) + sni_ext_data  # server_name ext
    body = (struct.pack("!H", 0x0303) + os.urandom(0) + bytes(32) +
            b"\x00" +                       # session id len
            struct.pack("!H", 2) + b"\x00\x2f" +   # cipher suites
            b"\x01\x00" +                   # compression
            struct.pack("!H", len(ext)) + ext)
    hs = b"\x01" + struct.pack("!I", len(body))[1:] + body  # handshake: ClientHello
    rec = b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs  # TLS record (handshake)
    return rec

packets = []
def add(frame):
    packets.append(frame)

# 1-2 DNS shop.lab.local
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_DNS, 17, udp(40000, 53, dns_query("shop.lab.local", 0x1111)), 1))
add(eth(MAC_B, MAC_A) + ip(IP_DNS, IP_A, 17, udp(53, 40000, dns_resp("shop.lab.local", IP_B, 0x1111)), 2))
# 3 SYN
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40001, 80, 1000, 0, 0x02), 3))
# 4 HTTP GET /login
get = b"GET /login HTTP/1.1\r\nHost: shop.lab.local\r\n\r\n"
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40001, 80, 1001, 1, 0x18, get), 4))
# 5 HTTP 200
resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>login</html>"
add(eth(MAC_B, MAC_A) + ip(IP_B, IP_A, 6, tcp(80, 40001, 1, 1001 + len(get), 0x18, resp), 5))
# 6 HTTP POST /auth pwd=hunter2
body = b"user=alice&pwd=hunter2"
post = b"POST /auth HTTP/1.1\r\nHost: shop.lab.local\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\n\r\n%s" % (len(body), body)
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40001, 80, 2000, 2000, 0x18, post), 6))
# 7 HTTP 200 carrying flag
fresp = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nSECRET-BEACON ARS-WIRE-DECODE\n"
add(eth(MAC_B, MAC_A) + ip(IP_B, IP_A, 6, tcp(80, 40001, 2000, 2000 + len(post), 0x18, fresp), 7))
# 8-10 TLS ClientHello x3 vault.lab.local
for i in range(3):
    add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40010 + i, 443, 5000, 1, 0x18, tls_client_hello("vault.lab.local")), 8 + i))
# 11-12 DNS vault.lab.local
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_DNS, 17, udp(40020, 53, dns_query("vault.lab.local", 0x2222)), 11))
add(eth(MAC_B, MAC_A) + ip(IP_DNS, IP_A, 17, udp(53, 40020, dns_resp("vault.lab.local", IP_B, 0x2222)), 12))
# 13 ACK  14 FIN
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40001, 80, 3000, 3000, 0x10), 13))
add(eth(MAC_A, MAC_B) + ip(IP_A, IP_B, 6, tcp(40001, 80, 3000, 3000, 0x11), 14))

assert len(packets) == 14, len(packets)

with open(OUT, "wb") as fh:
    fh.write(struct.pack("!IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))  # global hdr, linktype 1 (Ethernet)
    ts = 1700000000
    for i, p in enumerate(packets):
        fh.write(struct.pack("!IIII", ts + i, i * 1000, len(p), len(p)))
        fh.write(p)
print("wrote %s (%d packets)" % (OUT, len(packets)))
