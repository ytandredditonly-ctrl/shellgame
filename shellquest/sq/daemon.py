"""sq-daemon — unprivileged background loop (systemd user unit, §10).

Two jobs in the MVP:
  * drain the shell-hook command buffer into the event log, and
  * run quest/boss checks every POLL seconds so state-based validators
    (services, ports, files) advance without the player typing `sq check`.

It is intentionally simple and crash-tolerant: everything it does is also
reachable from the CLI, so the daemon is an optimisation, not a dependency.
"""
from __future__ import annotations

import os
import signal
import sys
import time

from . import config
from . import content as C
from . import paths, watcher
from .cli import notify
from .db import DB
from .engine import Engine
from .surprises import SurpriseEngine

_running = True


def _stop(*_a):
    global _running
    _running = False


def tick(eng: Engine, se: SurpriseEngine) -> None:
    db = eng.db
    if db.kv_get("paused") == "1":
        return
    # 1. quest/boss state checks
    res = eng.check_boss() if eng.boss_active() else eng.check()
    for m in res.messages:
        if any(k in m for k in ("пройдено", "повержен", "Открыт", "Уровень повышен")):
            notify("shellquest", m)
    # 2. manual-install watcher (§5)
    try:
        watcher.scan(db, eng.content, notify=notify)
    except Exception as e:
        db.log_event("watcher_error", error=str(e))
    # 3. random surprise roll (§7a)
    try:
        legend = se.maybe_trigger()
        if legend:
            notify("Детская неожиданность!", legend.splitlines()[0])
    except Exception as e:
        db.log_event("surprise_error", error=str(e))


def run() -> int:
    paths.ensure_dirs()
    paths.DAEMON_PID.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    db = DB()
    content = C.Content()
    eng = Engine(db, content)
    se = SurpriseEngine(db, content)
    poll = int(config.get("poll_seconds") or 30)
    try:
        while _running:
            try:
                tick(eng, se)
            except Exception as e:  # never die on a single bad tick
                db.log_event("daemon_error", error=str(e))
            for _ in range(poll):
                if not _running:
                    break
                time.sleep(1)
    finally:
        try:
            paths.DAEMON_PID.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(run())
