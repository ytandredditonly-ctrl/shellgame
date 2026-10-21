#!/usr/bin/env python3
import os, sys, stat
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
p = os.path.join(home, "terminal", "bin", "run.sh")
if not os.path.exists(p):
    sys.exit(1)
sys.exit(0 if os.stat(p).st_mode & stat.S_IXUSR else 1)
