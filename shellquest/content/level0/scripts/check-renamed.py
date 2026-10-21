#!/usr/bin/env python3
"""l0-q06: old_name must be gone (report presence checked by file_exists)."""
import os, sys
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
old = os.path.join(home, "terminal", "archive", "old_name")
sys.exit(0 if not os.path.exists(old) else 1)
