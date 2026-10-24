#!/bin/bash
# d3 «Веб-прокси» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d3"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d3 — Веб-прокси (Burp Suite).\nАрена shopfront (HTTP, порт 80).\nБраузер/прокси: 127.0.0.1:8080. Купи burpsuite: sq buy burpsuite.
EOF
echo "[dlc/d3] brief at $DIR/README.txt" >&2
exit 0
