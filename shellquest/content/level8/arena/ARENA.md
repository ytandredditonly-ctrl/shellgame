# Level 8 — crypto provisioning (no running container)
`sq-helperd` provisions files into `~/terminal/crypto/` via `apply_breakage`:
- `vault.gpg`     — symmetric gpg archive, weak password from `wordlist.txt`,
  containing the flag `CIPHER-OPEN-55`.
- `challenge.txt` — several learning hashes for the boss (md5/sha1/bcrypt).
- `final.gpg`     — final archive for the boss, flag `VAULT-CRACKED-404`.
All passwords are weak and drawn from the shipped wordlist (training only).
`level-setup.sh` already lays down `wordlist.txt`, `hashes.txt`, `notes.txt`.
