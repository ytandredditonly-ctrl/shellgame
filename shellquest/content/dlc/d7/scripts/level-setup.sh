#!/bin/bash
# d7 «SQL-инъекции» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d7"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d7 — SQL-инъекции (sqlmap).\nАрена dbshop (HTTP, порт 80), уязвим параметр id.\nНачни: curl 'http://dbshop/item?id=1'. Купи: sq buy sqlmap.
EOF
echo "[dlc/d7] brief at $DIR/README.txt" >&2
exit 0
