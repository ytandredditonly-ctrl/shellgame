#!/usr/bin/env python3
"""DLC d8 offline artifact: a tiny 802.11 beacon capture (capture.cap) whose
ESSID is readable by tshark/aircrack-ng. Training sample, fully offline.

Note: a cryptographically valid WPA2 4-way handshake cannot be synthesised
here, so the handshake/key parts are documented training values (see README).
The ESSID is genuinely parseable from the beacon.
"""
import struct, sys, os
OUT = sys.argv[1] if len(sys.argv) > 1 else "capture.cap"
ESSID = b"ARSENAL-LAB"
BSSID = bytes.fromhex("02aabbccdd01")

def beacon():
    fc = b"\x80\x00"                      # type: mgmt, subtype: beacon
    dur = b"\x00\x00"
    da = b"\xff\xff\xff\xff\xff\xff"
    sa = BSSID; bssid = BSSID
    seq = b"\x00\x00"
    mac = fc + dur + da + sa + bssid + seq
    ts = b"\x00" * 8; interval = b"\x64\x00"; cap = b"\x11\x04"
    ssid_ie = b"\x00" + bytes([len(ESSID)]) + ESSID
    rates_ie = bytes.fromhex("010482848b96")
    body = ts + interval + cap + ssid_ie + rates_ie
    return mac + body

packets = [beacon(), beacon()]
with open(OUT, "wb") as fh:
    fh.write(struct.pack("!IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 105))  # linktype 105 = IEEE802_11
    ts = 1700000000
    for i, p in enumerate(packets):
        fh.write(struct.pack("!IIII", ts + i, i, len(p), len(p)))
        fh.write(p)
print("wrote %s (ESSID %s)" % (OUT, ESSID.decode()))
