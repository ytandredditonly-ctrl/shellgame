#!/usr/bin/env python3
"""Boss d1 phase 2 — recon-net port map.

Grades the live arena: from inside a recon-net container, confirm every host
exposes exactly its known-good port set. Pass only when the whole map matches;
pending (exit 2) when the arena is down or Docker is unreachable — never a false
pass/fail. Works wherever the player can reach Docker (as the main-game arenas do).
"""
import subprocess
import sys

# host -> required open ports (the deterministic recon-net map)
EXPECTED = {
    "alpha": [22, 80],
    "beta": [80, 2222, 3306],
    "gamma": [80, 9000],
}
PROBE = "sq-d1-beta"  # any always-up node on the net to probe the others from

_SNIPPET = r"""
import socket, json, sys
exp = json.loads(sys.argv[1])
open_map = {}
for host, ports in exp.items():
    got = []
    for p in ports:
        try:
            s = socket.create_connection((host, p), 1.5); s.close(); got.append(p)
        except OSError:
            pass
    open_map[host] = got
print(json.dumps(open_map))
"""


def main() -> int:
    import json
    try:
        r = subprocess.run(
            ["docker", "exec", PROBE, "python3", "-c", _SNIPPET, json.dumps(EXPECTED)],
            capture_output=True, text=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return 2
    if r.returncode != 0 or not r.stdout.strip():
        return 2
    try:
        got = json.loads(r.stdout.strip())
    except ValueError:
        return 2
    for host, ports in EXPECTED.items():
        if sorted(got.get(host, [])) != sorted(ports):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
