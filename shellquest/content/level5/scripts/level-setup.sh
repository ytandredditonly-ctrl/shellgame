#!/bin/bash
set -u
mkdir -p "$HOME/terminal/siege"
printf 'SIEGE-HELD\n' > "$HOME/terminal/siege/flag.txt"
chmod 600 "$HOME/terminal/siege/flag.txt" 2>/dev/null || true
echo "[level5] attacker container is managed by sq-helperd (arena)" >&2
exit 0
