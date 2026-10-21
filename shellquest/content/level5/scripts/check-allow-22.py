#!/usr/bin/env python3
import subprocess, sys
out = ""
for cmd in (["ufw","status"],["nft","list","ruleset"],["iptables","-S"]):
    try:
        r = subprocess.run(["sudo","-n",*cmd], capture_output=True, text=True, timeout=5)
        out += r.stdout + r.stderr
    except Exception:
        pass
sys.exit(0 if "22" in out else 1)
