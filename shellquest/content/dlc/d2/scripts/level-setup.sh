#!/bin/bash
# d2 «Трафик» setup. Idempotent, game-owned under ~/sq-arsenal/d2.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/sq-arsenal/d2"
mkdir -p "$DIR"
python3 -I "$HERE/gen-pcap.py" "$DIR" >&2 || true
echo "[dlc/d2] artifacts under $DIR" >&2
exit 0
