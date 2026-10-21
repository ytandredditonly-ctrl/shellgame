#!/bin/bash
set -u
if [ -f "$HOME/.sq-l2.pids" ]; then
  while read -r pid; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done < "$HOME/.sq-l2.pids"
  rm -f "$HOME/.sq-l2.pids"
fi
rm -rf "$HOME/terminal/undead"
exit 0
