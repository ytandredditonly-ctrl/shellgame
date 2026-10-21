"""Manual-install watcher (§5).

The only sanctioned way to get a shop tool is `sq buy`. This watcher tails
`dpkg.log` and notices when a *shop* package is installed outside the game:

  * policy ``lenient`` (default, §14): allowed, but it earns nothing — we log
    the event once so the player understands tools come from the shop.
  * policy ``strict``: the package is removed again via sq-helperd and the
    player is told to use ``sq shop``.

Base system packages are never touched — only packages that appear in the
content's shop/unlock lists are in scope.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import config

DPKG_LOG = os.environ.get("SQ_DPKG_LOG", "/var/log/dpkg.log")
# e.g. "2026-10-21 03:00:00 install nmap:amd64 <none> 7.94+git..."
_INSTALL_RE = re.compile(r"^\S+\s+\S+\s+install\s+([a-z0-9][a-z0-9+._-]*)(?::\S+)?\s")


def _game_bought(db) -> set[str]:
    pkgs: set[str] = set()
    for r in db.events(limit=1000):
        if r["kind"] == "buy":
            try:
                pkgs.add(json.loads(r["payload"]).get("package", ""))
            except json.JSONDecodeError:
                pass
    pkgs.discard("")
    return pkgs


def shop_packages(content) -> set[str]:
    out: set[str] = set()
    for lvl in content.levels.values():
        out.update(lvl.unlock_packages)
        for item in lvl.shop:
            if item.get("package"):
                out.add(item["package"])
    return out


def scan(db, content, *, notify=None) -> list[str]:
    """Process new dpkg.log lines. Returns messages for any action taken."""
    log = Path(DPKG_LOG)
    if not log.is_file():
        return []
    try:
        size = log.stat().st_size
        offset = int(db.kv_get("dpkg_offset", "0") or 0)
        if offset > size:  # log rotated
            offset = 0
        with open(log, "r", errors="replace") as fh:
            fh.seek(offset)
            new = fh.read()
            db.kv_set("dpkg_offset", str(fh.tell()))
    except OSError:
        return []

    shop = shop_packages(content)
    bought = _game_bought(db)
    policy = config.get("install_policy")
    seen_lenient = set(json.loads(db.kv_get("dpkg_lenient_seen", "[]") or "[]"))
    msgs: list[str] = []

    for line in new.splitlines():
        m = _INSTALL_RE.match(line.strip())
        if not m:
            continue
        pkg = m.group(1)
        if pkg not in shop or pkg in bought:
            continue  # base package, or legitimately bought in-game
        if policy == "strict":
            from . import helper

            res = helper.remove_package(pkg, allow=sorted(shop))
            db.log_event("manual_install_reverted", package=pkg, ok=res.ok)
            msg = f"«{pkg}» установлен мимо магазина и удалён — инструменты берутся в sq shop."
            msgs.append(msg)
            if notify:
                notify("shellquest", msg)
        else:  # lenient
            if pkg not in seen_lenient:
                seen_lenient.add(pkg)
                db.log_event("manual_install_noted", package=pkg)
                msgs.append(
                    f"«{pkg}» установлен вручную (разрешено, но опыта не даёт — бери в sq shop)."
                )
    db.kv_set("dpkg_lenient_seen", json.dumps(sorted(seen_lenient)))
    return msgs
