#!/usr/bin/env python3
"""l0-q02: pass if the player has visited ~/terminal (from hook history)."""
import os, sys
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
target = os.path.realpath(os.path.join(home, "terminal"))
visited = os.environ.get("SQ_VISITED", "").splitlines()
cur = os.environ.get("SQ_PLAYER_CWD", "")
seen = {os.path.realpath(p) for p in visited if p}
if cur:
    seen.add(os.path.realpath(cur))
sys.exit(0 if target in seen else 1)
