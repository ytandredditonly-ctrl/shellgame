#!/usr/bin/env python3
# Boss p2: the recorded target must no longer be writable by others.
import os, sys, stat
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
tgt = os.path.join(home, "terminal", "guard", ".target")
if not os.path.exists(tgt):
    sys.exit(1)
path = open(tgt).read().strip()
if not os.path.exists(path):
    sys.exit(1)
sys.exit(0 if not (os.stat(path).st_mode & stat.S_IWOTH) else 1)
