#!/bin/bash
# d1 «Разведка» setup. Idempotent, game-owned: only writes a module brief under
# ~/sq-arsenal/d1. The recon-net arena is managed by sq-helperd (sq dlc start d1).
set -u
DIR="$HOME/sq-arsenal/d1"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d1 — Разведка (nmap)
Цели: alpha, beta, gamma в учебной сети recon-net (internal, без интернета).
Купи nmap: sq shop / sq buy nmap
Задания:  sq quests   ·   проверка: sq check   ·   ответ: sq answer <...>
EOF
echo "[dlc/d1] recon-net managed by sq-helperd; brief at $DIR/README.txt" >&2
exit 0
