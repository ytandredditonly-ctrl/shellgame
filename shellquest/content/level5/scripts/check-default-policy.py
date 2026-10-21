#!/usr/bin/env python3
import subprocess, sys
r = subprocess.run(["sudo","-n","ufw","status","verbose"], capture_output=True, text=True)
o = (r.stdout + r.stderr).lower()
sys.exit(0 if ("deny (incoming)" in o and "allow (outgoing)" in o) else 1)
