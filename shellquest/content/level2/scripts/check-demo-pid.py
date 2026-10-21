#!/usr/bin/env python3
import os, sys, subprocess
ans = (os.environ.get("SQ_ANSWER") or "").strip()
if not ans.isdigit():
    sys.exit(1)
r = subprocess.run(["pgrep", "-f", "sq-demo"], capture_output=True, text=True)
pids = set(r.stdout.split())
sys.exit(0 if ans in pids else 1)
