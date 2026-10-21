#!/usr/bin/env python3
# Accept the player's real umask, with or without the leading zero.
import os, sys, subprocess
ans = (os.environ.get("SQ_ANSWER") or "").strip().lstrip("0") or "0"
real = subprocess.run(["bash", "-c", "umask"], capture_output=True, text=True).stdout.strip()
real_n = real.lstrip("0") or "0"
sys.exit(0 if ans == real_n else 1)
