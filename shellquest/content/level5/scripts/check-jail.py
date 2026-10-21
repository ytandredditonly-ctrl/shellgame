#!/usr/bin/env python3
import subprocess, sys
r = subprocess.run(["sudo","-n","fail2ban-client","status","sshd"], capture_output=True, text=True)
sys.exit(0 if r.returncode == 0 and "Jail" in (r.stdout+r.stderr) else 1)
