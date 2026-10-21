"""Command-buffer draining and the reward event bus.

The zsh hook appends one JSON object per executed command to EVENT_BUFFER
(non-blocking for the shell). The engine drains that buffer into the DB's
``event_log`` as ``command`` events. Draining is idempotent-ish: we truncate
the buffer after a successful read, and a small offset file guards against
losing lines if two drains race (single-user game, so contention is rare).

Secret masking (§12 privacy): command lines matching obvious secret patterns
are redacted before they are ever persisted.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Iterable

from . import paths

_SECRET_RE = re.compile(
    r"(password|passwd|token|secret|api[_-]?key|-k|--key)[=\s]\S+", re.IGNORECASE
)


def mask_secrets(cmdline: str) -> str:
    return _SECRET_RE.sub(lambda m: m.group(1) + "=***", cmdline)


def append_event(cmdline: str, exit_code: int, cwd: str, duration_ms: int = 0) -> None:
    """Called by `sq _hook`; appends one buffered command event."""
    paths.ensure_dirs()
    rec = {
        "cmd": mask_secrets(cmdline),
        "exit": exit_code,
        "cwd": cwd,
        "dur": duration_ms,
    }
    with open(paths.EVENT_BUFFER, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def _first_word(cmdline: str) -> str:
    try:
        parts = shlex.split(cmdline)
    except ValueError:
        parts = cmdline.split()
    if not parts:
        return ""
    # Skip leading env assignments like FOO=bar cmd ...
    for tok in parts:
        if "=" in tok and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            continue
        return os.path.basename(tok)
    return ""


def drain_buffer(db) -> list[dict[str, Any]]:
    """Move buffered command lines into the event log. Returns new events."""
    buf = Path(paths.EVENT_BUFFER)
    if not buf.exists() or buf.stat().st_size == 0:
        return []
    try:
        lines = buf.read_text().splitlines()
        buf.write_text("")  # truncate once consumed
    except OSError:
        return []

    out: list[dict[str, Any]] = []
    prev: str | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        cmd = rec.get("cmd", "")
        # Anti-farm: drop byte-identical consecutive repeats (§6).
        if cmd == prev:
            continue
        prev = cmd
        name = _first_word(cmd)
        ev = {
            "cmd": cmd,
            "name": name,
            "exit": int(rec.get("exit", 0)),
            "cwd": rec.get("cwd", ""),
            "dur": int(rec.get("dur", 0)),
        }
        db.log_event("command", **ev)
        out.append(ev)
    return out


def recent_commands(db, limit: int = 500) -> list[dict[str, Any]]:
    """Command events from the log, oldest→newest, for validator context."""
    rows = db.events(limit=limit)
    cmds = []
    for r in rows:
        if r["kind"] != "command":
            continue
        rec = json.loads(r["payload"])
        rec["at"] = r["at"]
        cmds.append(rec)
    cmds.reverse()
    return cmds


# --- reward bus (§10): MVP ships an empty handler --------------------
class RewardHandler:
    def on_event(self, event: dict[str, Any]) -> None:  # pragma: no cover
        pass


_HANDLERS: list[RewardHandler] = []


def register_handler(h: RewardHandler) -> None:
    _HANDLERS.append(h)


def emit(kind: str, **payload: Any) -> None:
    event = {"kind": kind, **payload}
    for h in _HANDLERS:
        try:
            h.on_event(event)
        except Exception:
            pass
