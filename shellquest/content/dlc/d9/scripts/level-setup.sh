#!/bin/bash
# d9 «Веб-recon» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d9"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d9 — Веб-recon (nikto/gobuster/ffuf).\nАрена webmaze (HTTP, порт 80).\nНачни: nikto -h http://webmaze. Купи инструменты: sq buy nikto gobuster ffuf.
EOF
echo "[dlc/d9] brief at $DIR/README.txt" >&2
exit 0
