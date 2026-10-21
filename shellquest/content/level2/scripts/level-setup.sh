#!/bin/bash
# Level 2 setup. Spawns userspace marker processes so ps/kill quests work
# without root. Each is fully detached (fds -> /dev/null) and its PID is
# recorded for a precise teardown. The systemd/journal/cron quests additionally
# need sq-helperd (or sudo) and the shipped sq-demo.service; see README.
set -u
mkdir -p "$HOME/terminal/undead"
printf 'UNDEAD-CLEARED\n' > "$HOME/terminal/undead/flag.txt"
chmod 600 "$HOME/terminal/undead/flag.txt" 2>/dev/null || true
: > "$HOME/.sq-l2.pids"

_spawn() { # name
  local name="$1"
  pgrep -f "$name" >/dev/null 2>&1 && return 0
  bash -c "exec -a '$name' bash -c 'while :; do sleep 60; done'" \
    </dev/null >/dev/null 2>&1 &
  echo $! >> "$HOME/.sq-l2.pids"
  disown 2>/dev/null || true
}
_spawn sq-demo
_spawn sq-runaway
_spawn sq-miner
exit 0
