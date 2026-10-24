#!/bin/bash
# d4 «Эксплуатация» setup. Idempotent, game-owned. Arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d4"
mkdir -p "$DIR"
cat > "$DIR/README.txt" <<'EOF'
Модуль d4 — Эксплуатация (Metasploit).\nАрена breach: hostname breach-core, 21/tcp vsFTPd 2.3.4, бэкдор-шелл 6200/tcp.\nКупи: sq buy metasploit-framework.
EOF
echo "[dlc/d4] brief at $DIR/README.txt" >&2
exit 0
