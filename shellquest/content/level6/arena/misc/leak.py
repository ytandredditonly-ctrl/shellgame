#!/usr/bin/env python3
"""misc host: periodically sends a cleartext credential to web so a tcpdump
on the lab network catches it (level-6 q05). Training only."""
import time, urllib.request
while True:
    try:
        urllib.request.urlopen(
            urllib.request.Request("http://web/login",
                data=b"user=svc&pwd=hunter2-leak", method="POST"), timeout=3)
    except Exception:
        pass
    time.sleep(5)
