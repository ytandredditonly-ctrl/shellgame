#!/usr/bin/env python3
"""Boss d8 phase 1 — ESSID + BSSID from the capture.

Offline grader: parse the shipped capture.cap (a real 802.11 beacon, linktype
105) and confirm the beacon advertises the expected ESSID and BSSID — exactly
what the player reads with aircrack-ng/tshark. Pass on a match; pending (exit 2)
when the artifact is missing or unparsable — never a false pass/fail.
"""
import os
import struct
import sys

HOME = os.environ.get("SQ_HOME") or os.path.expanduser("~")
CAP = os.path.join(HOME, "sq-arsenal", "d8", "capture.cap")
EXPECT_ESSID = b"ARSENAL-LAB"
EXPECT_BSSID = bytes.fromhex("02aabbccdd01")


def parse_first_beacon(data: bytes):
    # pcap global header = 24 bytes; then per-packet 16-byte records.
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack("!IIII", data[off:off + 16])
        off += 16
        pkt = data[off:off + incl]
        off += incl
        if len(pkt) < 36 or pkt[0:2] != b"\x80\x00":
            continue
        bssid = pkt[16:22]
        body = pkt[24:]
        # fixed params: timestamp(8)+interval(2)+cap(2) = 12, then tagged IEs
        ies = body[12:]
        i = 0
        essid = None
        while i + 2 <= len(ies):
            tag, ln = ies[i], ies[i + 1]
            val = ies[i + 2:i + 2 + ln]
            if tag == 0:  # SSID
                essid = val
                break
            i += 2 + ln
        return essid, bssid
    return None, None


def main() -> int:
    if not os.path.isfile(CAP):
        return 2
    try:
        essid, bssid = parse_first_beacon(open(CAP, "rb").read())
    except (OSError, struct.error):
        return 2
    return 0 if essid == EXPECT_ESSID and bssid == EXPECT_BSSID else 2


if __name__ == "__main__":
    sys.exit(main())
