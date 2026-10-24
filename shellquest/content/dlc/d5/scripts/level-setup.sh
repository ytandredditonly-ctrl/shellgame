#!/bin/bash
# d5 «Пароли офлайн» setup. Idempotent, game-owned under ~/sq-arsenal/d5.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/sq-arsenal/d5"
mkdir -p "$DIR"
bash "$HERE/gen-hashes.sh" "$DIR" >&2 || true
echo "[dlc/d5] artifacts under $DIR" >&2
exit 0
