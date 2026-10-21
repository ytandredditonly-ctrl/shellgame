"""Filesystem locations for shellquest, following the XDG base-dir spec."""
from __future__ import annotations

import os
from pathlib import Path


def _xdg(env: str, default: Path) -> Path:
    val = os.environ.get(env)
    return Path(val).expanduser() if val else default


HOME = Path.home()

# ~/.local/share/shellquest — state, db, buffer, logs (§10 of the TZ).
DATA_DIR = _xdg("XDG_DATA_HOME", HOME / ".local" / "share") / "shellquest"
# ~/.config/shellquest — config.yaml.
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", HOME / ".config") / "shellquest"
# ~/.local/state/shellquest — runtime sockets / pid.
STATE_DIR = _xdg("XDG_STATE_HOME", HOME / ".local" / "state") / "shellquest"

DB_PATH = DATA_DIR / "state.db"
# Append-only command buffer written by the shell hook (non-blocking).
EVENT_BUFFER = DATA_DIR / "events.jsonl"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DAEMON_PID = STATE_DIR / "daemon.pid"

# Content ships alongside the package by default, overridable for dev.
_pkg_content = Path(__file__).resolve().parent.parent / "content"
CONTENT_DIR = Path(os.environ.get("SQ_CONTENT_DIR", _pkg_content))


def ensure_dirs() -> None:
    for d in (DATA_DIR, CONFIG_DIR, STATE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def helper_socket() -> str:
    """A short, writable Unix-socket path (AF_UNIX caps at ~108 bytes).

    Prefer $XDG_RUNTIME_DIR (e.g. /run/user/1000), then a per-uid /tmp dir,
    then the state dir as a last resort.
    """
    uid = os.getuid()
    candidates = []
    rt = os.environ.get("XDG_RUNTIME_DIR")
    if rt:
        candidates.append(Path(rt) / "shellquest")
    candidates.append(Path(f"/tmp/shellquest-{uid}"))
    candidates.append(STATE_DIR)
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        sp = base / "helperd.sock"
        if len(str(sp)) < 104:
            return str(sp)
    return str(STATE_DIR / "helperd.sock")
