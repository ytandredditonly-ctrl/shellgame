#!/usr/bin/env python3
# Pass once fail2ban reports at least one banned IP in the sshd jail.
import subprocess, sys, re
r = subprocess.run(["sudo","-n","fail2ban-client","status","sshd"], capture_output=True, text=True)
m = re.search(r"Currently banned:\s*(\d+)", r.stdout)
sys.exit(0 if (m and int(m.group(1)) > 0) else 1)
