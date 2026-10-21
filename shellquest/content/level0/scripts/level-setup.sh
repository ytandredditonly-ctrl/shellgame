#!/bin/bash
# Level 0 setup: scatter the Architect's leftovers under ~/terminal.
# Idempotent — safe to re-run. Touches only ~/terminal (§12 isolation).
set -u
T="$HOME/terminal"

mkdir -p "$T/archive" "$T/notes" "$T/scraps" "$T/shared" "$T/bin" \
         "$T/vault/a" "$T/vault/b/c" "$T/vault/d"

# notes/welcome.txt — code word on the last line (l0-q03).
cat > "$T/notes/welcome.txt" <<'EOF'
Оператор, если ты это читаешь — я не вернусь.
Терминал твой. Наведи порядок и не доверяй тому, что оставлено автоматикой.
Кодовое слово доступа: nightfall
EOF

# A buried file with PASS= for l0-q07 (grep hunt).
echo "config load ok" > "$T/archive/notes_dump.txt"
printf 'service=idle\nPASS=granite\nmode=safe\n' > "$T/archive/secret.log"

# archive/old_name for the rename quest (l0-q06). Reset if a stale report exists.
rm -f "$T/archive/old_name"
printf 'legacy report body\n' > "$T/archive/old_name"

# scraps: 5 junk .tmp + 2 keepers without extension (l0-q05).
for i in 1 2 3 4 5; do echo "junk $i" > "$T/scraps/cache_$i.tmp"; done
echo "keep me"   > "$T/scraps/manifest"
echo "keep me 2" > "$T/scraps/ledger"

# vault fragments for the boss: ARCH + ITECT + -77 + 31  => ARCHITECT-7731
printf 'ARCH'  > "$T/vault/a/part_1"
printf 'ITECT' > "$T/vault/b/c/part_2"
printf -- '-77' > "$T/vault/d/part_3"
printf '31'    > "$T/vault/part_4"
# Clean any previously assembled key so re-runs start fresh.
rm -f "$T/vault/key.txt"

exit 0
