#!/bin/bash
# d6 «Онлайн-вход» setup. Writes the wordlist (12 passwords) + brief. sshd/http
# arena is managed by sq-helperd.
set -u
DIR="$HOME/sq-arsenal/d6"
mkdir -p "$DIR"
cat > "$DIR/wordlist.txt" <<'EOF'
123456
letmein
password1
dragon
qwerty
apple
sunshine
trustno1
monkey
football
iloveyou
admin123
EOF
cat > "$DIR/README.txt" <<'EOF'
Модуль d6 — Онлайн-вход (Hydra). Арена loginbox: SSH (user admin) и HTTP-форма.
1) Составь users.txt (один логин в строке, напр. admin) в этой папке.
2) Пароли — в wordlist.txt (12 шт). SSH: hydra -L users.txt -P wordlist.txt ssh://loginbox
3) HTTP-форма (порт 8080): http-post-form "/login:user=^USER^&pass=^PASS^:F=FAIL"
EOF
echo "[dlc/d6] wordlist + brief at $DIR" >&2
exit 0
