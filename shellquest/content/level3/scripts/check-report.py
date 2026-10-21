#!/usr/bin/env python3
# Run the player's report.sh and confirm it prints the known 404 count and top IP.
import os, subprocess, sys
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
rpt = os.path.join(home, "terminal", "logs", "report.sh")
if not os.path.isfile(rpt):
    sys.exit(1)
try:
    out = subprocess.run(["bash", rpt], capture_output=True, text=True,
                         timeout=8, cwd=os.path.dirname(rpt)).stdout
except Exception:
    sys.exit(1)
sys.exit(0 if ("552" in out and "10.0.0.7" in out) else 1)
