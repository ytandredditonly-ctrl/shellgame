"""Game configuration (~/.config/shellquest/config.yaml).

Loaded lazily and merged over defaults. Anything missing falls back to the
default, so an absent or partial file is always valid.
"""
from __future__ import annotations

from typing import Any

import yaml

from . import paths

DEFAULTS: dict[str, Any] = {
    # interface
    "quiet": False,            # suppress in-terminal notification lines
    "prompt": False,           # enable the prompt indicator hint (see hook)
    # surprises (§7a)
    "surprises": True,
    "surprise_chance": 0.15,
    "surprise_min_session_minutes": 20,
    "surprise_cooldown_minutes": 60,
    "surprise_active_window_minutes": 5,
    "surprise_track_max_run": 2,   # don't repeat a track >2x in a row
    # daemon
    "poll_seconds": 30,
    # manual-install policy for the dpkg watcher (§5): lenient|strict
    "install_policy": "lenient",
    # helper (empty -> computed at runtime via paths.helper_socket())
    "helper_socket": "",
    "helper_dry_run": False,   # when true, helper logs ops without executing
}


_cache: dict[str, Any] | None = None


def load(force: bool = False) -> dict[str, Any]:
    global _cache
    if _cache is not None and not force:
        return _cache
    cfg = dict(DEFAULTS)
    try:
        if paths.CONFIG_PATH.is_file():
            data = yaml.safe_load(paths.CONFIG_PATH.read_text()) or {}
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, yaml.YAMLError):
        pass
    _cache = cfg
    return cfg


def get(key: str, default: Any = None) -> Any:
    return load().get(key, DEFAULTS.get(key, default))


def write_default() -> None:
    """Create a commented config file if none exists."""
    paths.ensure_dirs()
    if paths.CONFIG_PATH.exists():
        return
    paths.CONFIG_PATH.write_text(
        "# shellquest configuration. Delete a key to use its default.\n"
        + yaml.safe_dump(DEFAULTS, sort_keys=True, allow_unicode=True)
    )
