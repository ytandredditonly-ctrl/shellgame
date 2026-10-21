#!/bin/bash
# Level 8 provisioning (run by sq-helperd apply_breakage, or standalone).
# Creates crackable learning artefacts in ~/terminal/crypto. All passwords are
# WEAK and drawn from the shipped wordlist — training only, local arena.
set -u
C="$HOME/terminal/crypto"
mkdir -p "$C"

cat > "$C/wordlist.txt" <<'WL'
password
letmein
dragon
sunshine
terminal
architect
matrix
monkey
shadow
master
WL

# q01/q04/q05 learning hashes (md5, sha1, md5) of weak words
{
  printf 'dragon'   | md5sum  | cut -d' ' -f1
  printf 'sunshine' | sha1sum | cut -d' ' -f1
  printf 'monkey'   | md5sum  | cut -d' ' -f1
} > "$C/hashes.txt"

printf 'operator log: nothing to see here\n' > "$C/notes.txt"

_enc() { # <passphrase> <plaintext-file> <out>
  gpg --batch --yes --pinentry-mode loopback --passphrase "$1" \
      -c --cipher-algo AES256 -o "$3" "$2" 2>/dev/null
}

# q06 vault.gpg — weak pass "architect", flag inside
printf 'flag: CIPHER-OPEN-55\n' > "$C/.plain"
_enc architect "$C/.plain" "$C/vault.gpg"

# boss: challenge.txt (md5/sha1/sha256) + final.gpg (weak pass "matrix")
{
  printf 'shadow' | md5sum   | cut -d' ' -f1
  printf 'master' | sha1sum  | cut -d' ' -f1
  printf 'matrix' | sha256sum| cut -d' ' -f1
} > "$C/challenge.txt"
printf 'flag: VAULT-CRACKED-404\n' > "$C/.plain"
_enc matrix "$C/.plain" "$C/final.gpg"
rm -f "$C/.plain"
echo "level8 provisioned in $C"
exit 0
