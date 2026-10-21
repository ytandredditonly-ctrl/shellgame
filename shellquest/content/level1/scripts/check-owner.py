#!/usr/bin/env python3
# Pass if the answer matches the real owner name of secret.log.
import os, sys, pwd
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
p = os.path.join(home, "terminal", "archive", "secret.log")
ans = (os.environ.get("SQ_ANSWER") or "").strip()
if not ans or not os.path.exists(p):
    sys.exit(1)
try:
    owner = pwd.getpwuid(os.stat(p).st_uid).pw_name
except KeyError:
    owner = str(os.stat(p).st_uid)
sys.exit(0 if ans == owner else 1)
