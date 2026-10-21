#!/usr/bin/env python3
import subprocess, sys
r = subprocess.run(["pgrep", "-f", "sq-runaway"], capture_output=True, text=True)
sys.exit(0 if not r.stdout.strip() else 1)
