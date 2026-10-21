#!/usr/bin/env python3
import os, sys
ans = (os.environ.get("SQ_ANSWER") or "").strip()
sys.exit(0 if ans.isdigit() and int(ans) == os.getuid() else 1)
