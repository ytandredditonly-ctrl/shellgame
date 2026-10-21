#!/bin/bash
# Start a harmless, fully-detached TCP listener named sq-listener-<port>.
# fds go to /dev/null so it never holds any terminal; its PID is recorded so
# teardown kills exactly that process (never a broad pkill).
set -u
PORT="$SQ_SP_PORT"
bash -c "exec -a 'sq-listener-$PORT' python3 -c '
import socket,time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((\"127.0.0.1\",$PORT)); s.listen(1)
while True:
    try: c,_=s.accept(); c.close()
    except Exception: time.sleep(1)
'" </dev/null >/dev/null 2>&1 &
echo $! > "$HOME/.sq-listener.pid"
echo "$PORT" > "$HOME/.sq-listener-port"
disown 2>/dev/null || true
exit 0
