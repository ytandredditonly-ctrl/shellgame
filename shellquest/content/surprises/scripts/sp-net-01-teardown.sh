#!/bin/bash
# Kill exactly the recorded listener PID; clean up markers.
set -u
PID=$(cat "$HOME/.sq-listener.pid" 2>/dev/null)
[ -n "${PID:-}" ] && kill "$PID" 2>/dev/null || true
rm -f "$HOME/.sq-listener.pid" "$HOME/.sq-listener-port"
exit 0
