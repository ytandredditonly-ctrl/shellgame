#!/usr/bin/env python3
import os, sys
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
logs = os.path.join(home, "terminal", "logs")
src, dst = os.path.join(logs, "access.log"), os.path.join(logs, "clean.log")
if not (os.path.isfile(src) and os.path.isfile(dst)):
    sys.exit(1)
a = open(src).read().splitlines()
c = open(dst).read().splitlines()
ok = (len(a) == len(c)) and ("ERROR" not in open(dst).read())
sys.exit(0 if ok else 1)
