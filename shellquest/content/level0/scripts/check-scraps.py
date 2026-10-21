#!/usr/bin/env python3
"""l0-q05: no *.tmp left in scraps, both keepers still present."""
import os, sys, glob
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
scraps = os.path.join(home, "terminal", "scraps")
if not os.path.isdir(scraps):
    sys.exit(1)
tmp_left = glob.glob(os.path.join(scraps, "*.tmp"))
keepers_ok = all(os.path.exists(os.path.join(scraps, k)) for k in ("manifest", "ledger"))
sys.exit(0 if (not tmp_left and keepers_ok) else 1)
