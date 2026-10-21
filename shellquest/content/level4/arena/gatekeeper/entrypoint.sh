#!/bin/bash
set -e
# Install the player's mounted public key for root (if provided).
if [ -f /opt/player_key.pub ]; then
  mkdir -p /root/.ssh && chmod 700 /root/.ssh
  cp /opt/player_key.pub /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi
# echo service on 9000: answer "pong-42" to any line containing "ping".
socat -T1 TCP-LISTEN:9000,reuseaddr,fork SYSTEM:'read l; echo pong-42' &
python3 /opt/web.py &
exec /usr/sbin/sshd -D -e
