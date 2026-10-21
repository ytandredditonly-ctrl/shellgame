#!/usr/bin/env python3
# Boss p1: answer must be the path of the world-writable file.
import os, sys
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
tgt = os.path.join(home, "terminal", "guard", ".target")
ans = (os.environ.get("SQ_ANSWER") or "").strip()
if not ans or not os.path.exists(tgt):
    sys.exit(1)
want = open(tgt).read().strip()
sys.exit(0 if os.path.realpath(os.path.expanduser(ans)) == os.path.realpath(want) else 1)
