#!/bin/bash
# d10 «Терминальный захват» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d10"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d10 — Терминальный захват (tcpdump).\nАрена serverbox (HTTP, порт 80), генерит трафик с X-Token и флагом.\nКупи: sq buy tcpdump.
EOF
echo "[dlc/d10] brief at $DIR/README.txt" >&2
exit 0
