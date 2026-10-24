#!/bin/bash
# final «Полигон Архитектора» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/final"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Финал — Полигон Архитектора.\nАрена proving-ground: веб 80, SSH 22, флаг-служба 7777.\nИнструменты уже куплены в d1–d10. Открой босса: sq check; затем sq boss start.
EOF
echo "[dlc/final] brief at $DIR/README.txt" >&2
exit 0
