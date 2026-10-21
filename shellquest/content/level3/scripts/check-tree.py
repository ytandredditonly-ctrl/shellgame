#!/usr/bin/env python3
# Accept the real dpkg version of `tree`, or "none" when it is not installed.
import os, sys, subprocess
ans = (os.environ.get("SQ_ANSWER") or "").strip().lower()
r = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "tree"],
                   capture_output=True, text=True)
if r.returncode != 0 or not r.stdout.strip():
    sys.exit(0 if ans == "none" else 1)
ver = r.stdout.strip().lower()
sys.exit(0 if ans in (ver, ver.split("-")[0], ver.split("+")[0]) else 1)
