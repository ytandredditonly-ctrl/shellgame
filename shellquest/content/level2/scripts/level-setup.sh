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

_alive() { # name — true if a process with this exact argv0 exists
  for p in /proc/[0-9]*/cmdline; do
    [ -r "$p" ] || continue
    IFS= read -r -d '' a0 < "$p" 2>/dev/null
    case "${a0##*/}" in "$1") return 0;; esac
  done
  return 1
}
_spawn() { # name
  local name="$1"
  _alive "$name" && return 0
  # setsid -> own session, so it survives the spawning process exiting; fds to
  # /dev/null so it never holds a terminal. argv0 is the recognisable name.
  setsid bash -c "exec -a '$name' sleep infinity" </dev/null >/dev/null 2>&1 &
  echo $! >> "$HOME/.sq-l2.pids"
  disown 2>/dev/null || true
}
_spawn sq-demo
_spawn sq-runaway
_spawn sq-miner
exit 0
