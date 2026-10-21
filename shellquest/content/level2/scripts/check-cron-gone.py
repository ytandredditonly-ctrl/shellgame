#!/usr/bin/env python3
# Pass if no sq-* reviver cron entry remains in the common locations.
import glob, os, sys, subprocess
hits = []
for p in ["/etc/crontab"] + glob.glob("/etc/cron.d/*"):
    try:
        if "sq-" in open(p).read() and "revive" in open(p).read():
            hits.append(p)
    except OSError:
        pass
u = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
if "revive" in (u.stdout or ""):
    hits.append("user-crontab")
sys.exit(0 if not hits else 1)
