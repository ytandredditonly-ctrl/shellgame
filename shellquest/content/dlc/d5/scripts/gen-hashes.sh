#!/bin/bash
# DLC d5 offline artifacts. Idempotent. Weak, training-only passwords.
set -u
DIR="${1:-$HOME/sq-arsenal/d5}"
mkdir -p "$DIR"
md5()  { printf '%s' "$1" | python3 -I -c 'import sys,hashlib;print(hashlib.md5(sys.stdin.buffer.read()).hexdigest())'; }

# hashes.txt — four raw MD5 hashes; all four passwords are in wordlist.txt
{ md5 letmein; md5 password1; md5 dragon; md5 qwerty; } > "$DIR/hashes.txt"

# slowfast.txt — a fast MD5 (apple, crackable) vs a slow salted sha512crypt (survives)
{ md5 apple
  openssl passwd -6 -salt arsenal 'Zx9KpLm2Q7wREH' ; } > "$DIR/slowfast.txt"

# shadow.sample + passwd.sample — for `unshadow` then crack (password: sunshine)
S6=$(openssl passwd -6 -salt sq4242 sunshine)
printf 'victim:%s:19700:0:99999:7:::\n' "$S6" > "$DIR/shadow.sample"
printf 'victim:x:1001:1001:victim:/home/victim:/bin/bash\n' > "$DIR/passwd.sample"

# boss p2 key hash (password: trustno1)
md5 trustno1 > "$DIR/key.hash"

# boss p1 challenge.txt — mixed algorithms to identify
{ md5 alpha; printf '%s\n' "$(printf '%s' beta | sha1sum | cut -d' ' -f1)";
  printf '%s\n' "$(printf '%s' gamma | sha256sum | cut -d' ' -f1)";
  openssl passwd -6 -salt mixsalt delta; } > "$DIR/challenge.txt"

# secret.enc — opened with the cracked key (trustno1); contains the module flag
printf 'ARS-HASH-CRACK\n' | openssl enc -aes-256-cbc -pbkdf2 -salt -pass pass:trustno1 \
    -out "$DIR/secret.enc" 2>/dev/null

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
Модуль d5 — Пароли офлайн (John / Hashcat)
Файлы (учебные, слабые пароли):
  hashes.txt    — 4 сырых MD5 (взломай словарём)
  slowfast.txt  — быстрый MD5 vs медленный sha512crypt ($6$)
  shadow.sample + passwd.sample — для `unshadow`
  key.hash      — ключевой хеш босса
  challenge.txt — набор разных алгоритмов (опознай)
  secret.enc    — AES-файл, пароль = взломанный ключ; внутри флаг
  wordlist.txt  — словарь
Пример: john --wordlist=wordlist.txt hashes.txt ; john --show hashes.txt
Открыть секрет: openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:<ключ> -in secret.enc
EOF
echo "[dlc/d5] offline artifacts in $DIR" >&2
exit 0
