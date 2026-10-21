"""«Детская неожиданность» — surprise events (§7a).

Short, self-contained side-tasks on three tracks (crypto / net / linux) that do
not touch level progression. Each run is parametrised (fresh flag/port/name), so
answers can't be memorised; only a SHA-256 of the expected value is kept in
state. Events never punish breaks: no timer, survives shutdown, drop is free.

Isolation (§7a/§12): events touch only `sq-*` things and `~/sq-drop` /
`~/sq-sandbox`. Setup/teardown run via content scripts; teardown fully reverts.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import string
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import config, events, paths, schema
from .validators import Context, run_validator

REWARD_FIRST = (30, 25)   # xp, coins — first solve of an id
REWARD_REPEAT = (0, 10)   # repeat with new params

WORDS = ["lantern", "granite", "harbor", "copper", "willow", "cobalt",
         "ember", "quartz", "meadow", "falcon"]


def _sha(s: str) -> str:
    return hashlib.sha256(str(s).encode()).hexdigest()


# --- parameter generators --------------------------------------------
def _gen(spec: str, rng: random.Random) -> str:
    if spec == "random_flag":
        return "SURP-" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=6))
    if spec == "random_word":
        return rng.choice(WORDS)
    if spec == "random_name":
        return "".join(rng.choices(string.ascii_lowercase, k=8)) + ".dat"
    if spec == "random_port":
        return str(rng.randint(20000, 40000))
    if spec == "random_int":
        return str(rng.randint(2, 99))
    return spec  # literal


def _render(value: Any, params: dict[str, str]) -> Any:
    """Substitute {{params.X}} and {{params.X | sha256}} in strings/dicts/lists."""
    if isinstance(value, dict):
        return {k: _render(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, params) for v in value]
    if isinstance(value, str):
        import re

        def repl(m):
            name = m.group(1).strip()
            pipe = (m.group(2) or "").strip()
            val = params.get(name, "")
            return _sha(val) if pipe == "sha256" else val

        return re.sub(r"\{\{\s*params\.([a-zA-Z0-9_]+)\s*(?:\|\s*([a-z0-9]+)\s*)?\}\}",
                      repl, value)
    return value


@dataclass
class Surprise:
    id: str
    track: str
    title: str
    brief: str
    validators: list[dict]
    story: str = ""
    min_level: int = 0
    requires_packages: list[str] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)
    hints: list[str] = field(default_factory=list)
    setup: str | None = None
    teardown: str | None = None
    codex: str | None = None
    dir: Path = field(default=Path("."))


def load_surprises(content_dir: Path) -> dict[str, Surprise]:
    out: dict[str, Surprise] = {}
    sdir = content_dir / "surprises"
    if not sdir.is_dir():
        return out
    for f in sorted(sdir.glob("*.yaml")):
        d = yaml.safe_load(f.read_text()) or {}
        schema.validate(d, schema.SURPRISE_SCHEMA, str(f))
        out[d["id"]] = Surprise(
            id=d["id"], track=d["track"], title=d.get("title", d["id"]),
            brief=d.get("brief", ""), validators=list(d.get("validators", [])),
            story=d.get("story", ""), min_level=int(d.get("min_level", 0)),
            requires_packages=list(d.get("requires_packages", [])),
            params=dict(d.get("params", {})), hints=list(d.get("hints", [])),
            setup=d.get("setup"), teardown=d.get("teardown"), codex=d.get("codex"),
            dir=sdir,
        )
    return out


class SurpriseEngine:
    def __init__(self, db, content):
        self.db = db
        self.content = content
        self.pool = load_surprises(content.dir)

    # -- state (kv-backed) --------------------------------------------
    def _active(self) -> dict | None:
        raw = self.db.kv_get("surprise_active")
        return json.loads(raw) if raw else None

    def _solved_ids(self) -> set[str]:
        return set(json.loads(self.db.kv_get("surprises_solved", "[]") or "[]"))

    def _track_history(self) -> list[str]:
        return json.loads(self.db.kv_get("surprise_track_history", "[]") or "[]")

    def active_id(self) -> str | None:
        a = self._active()
        return a["id"] if a else None

    # -- selection ----------------------------------------------------
    def _eligible(self, track: str | None) -> list[Surprise]:
        from .db import DB  # noqa

        level = self.db.profile()["level"] if self.db.profile() else 0
        opened = self.db.opened_commands()
        out = []
        hist = self._track_history()
        run_cap = config.get("surprise_track_max_run")
        for s in self.pool.values():
            if s.min_level > level:
                continue
            if track and s.track != track:
                continue
            # package gate: required tools must be installed or already opened
            if s.requires_packages and not all(
                self._pkg_ok(p, opened) for p in s.requires_packages
            ):
                continue
            # avoid a track appearing > cap times in a row
            if not track and len(hist) >= run_cap and all(h == s.track for h in hist[-run_cap:]):
                continue
            out.append(s)
        return out

    @staticmethod
    def _pkg_ok(pkg: str, opened: set[str]) -> bool:
        if pkg in opened:
            return True
        try:
            return subprocess.run(["dpkg", "-s", pkg], capture_output=True,
                                  timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    # -- lifecycle ----------------------------------------------------
    def start(self, track: str | None = None) -> tuple[bool, str]:
        if self._active():
            return False, "Ивент уже идёт — см. sq surprise status."
        if not config.get("surprises"):
            return False, "Ивенты выключены в конфиге (surprises: false)."
        candidates = self._eligible(track)
        if not candidates:
            return False, "Нет подходящих ивентов для текущего уровня/набора утилит."
        rng = random.Random()
        s = rng.choice(candidates)
        params = {k: _gen(v, rng) for k, v in s.params.items()}
        # run setup with params in the environment
        self._run_script(s, s.setup, params)
        active = {"id": s.id, "params": params, "started_at": time.time(),
                  "track": s.track}
        self.db.kv_set("surprise_active", json.dumps(active))
        hist = (self._track_history() + [s.track])[-5:]
        self.db.kv_set("surprise_track_history", json.dumps(hist))
        self.db.log_event("surprise_started", id=s.id, track=s.track)
        events.emit("surprise_started", id=s.id, track=s.track)
        return True, self._legend(s, params)

    def status(self) -> str:
        a = self._active()
        if not a:
            return "Активного ивента нет. Запуск: sq surprise [crypto|net|linux]."
        s = self.pool.get(a["id"])
        if not s:
            return "Активный ивент (контент не найден)."
        return self._legend(s, a["params"])

    def drop(self) -> str:
        a = self._active()
        if not a:
            return "Активного ивента нет."
        s = self.pool.get(a["id"])
        if s:
            self._run_script(s, s.teardown, a["params"])
        self.db.kv_set("surprise_active", "")
        cd = config.get("surprise_cooldown_minutes") * 60
        self.db.kv_set("surprise_cooldown_until", str(time.time() + cd))
        self.db.log_event("surprise_dropped", id=a["id"])
        events.emit("surprise_dropped", id=a["id"])
        return "Ивент сброшен и откатан. Штрафа нет; кулдаун запущен."

    def submit(self, answer: str | None = None, flag: str | None = None) -> tuple[bool, str]:
        a = self._active()
        if not a:
            return False, "Активного ивента нет."
        s = self.pool.get(a["id"])
        if not s:
            return False, "Контент ивента не найден."
        events.drain_buffer(self.db)
        cmds = events.recent_commands(self.db)
        ctx = Context(
            db=self.db, content_dir=self.content.dir, scripts_dir=s.dir / "scripts",
            commands=cmds, cwd=self.db.kv_get("player_cwd", os.path.expanduser("~")) or "",
            answer=answer, flag=flag, env=dict(os.environ),
        )
        specs = [_render(v, a["params"]) for v in s.validators]
        results = [run_validator(ctx, v) for v in specs]
        if results and all(r == "pass" for r in results):
            return True, self._solve(s, a)
        return False, "Пока не то. Проверь ещё раз или возьми подсказку (sq hint surprise)."

    def _solve(self, s: Surprise, active: dict) -> str:
        solved = self._solved_ids()
        first = s.id not in solved
        xp, coins = REWARD_FIRST if first else REWARD_REPEAT
        self.db.add_xp_coins(xp, coins)
        if first:
            solved.add(s.id)
            self.db.kv_set("surprises_solved", json.dumps(sorted(solved)))
        # teardown + clear + cooldown
        self._run_script(s, s.teardown, active["params"])
        self.db.kv_set("surprise_active", "")
        cd = config.get("surprise_cooldown_minutes") * 60
        self.db.kv_set("surprise_cooldown_until", str(time.time() + cd))
        self.db.log_event("surprise_solved", id=s.id, xp=xp, coins=coins, first=first)
        events.emit("surprise_solved", id=s.id)
        msg = f"Ивент решён: {s.title} (+{xp} XP, +{coins} монет)."
        if first and s.codex:
            msg += f"\nОткрыта карточка-разбор в кодексе: {s.id}."
        return msg

    def buy_hint(self, engine) -> tuple[bool, str]:
        a = self._active()
        if not a:
            return False, "Активного ивента нет."
        s = self.pool.get(a["id"])
        if not s or not s.hints:
            return False, "У ивента нет подсказок."
        key = f"surprise:{s.id}"
        opened = self.db.hints_opened(key)
        from .content import HINT_PRICES
        if opened >= len(s.hints):
            return True, "\n".join(f"[{i+1}] {h}" for i, h in enumerate(s.hints))
        price = HINT_PRICES[min(opened, len(HINT_PRICES) - 1)]
        p = self.db.profile()
        if p["coins"] < price:
            return False, f"Не хватает монет: нужно {price}, есть {p['coins']}."
        self.db.spend_coins(price)
        self.db.buy_hint(key, opened + 1)
        shown = "\n".join(f"[{i+1}] {s.hints[i]}" for i in range(opened + 1))
        return True, f"(−{price} монет)\n{shown}"

    # -- random trigger (daemon) --------------------------------------
    def maybe_trigger(self) -> str | None:
        """Called each daemon tick. Returns a legend if an event fired."""
        if not config.get("surprises") or self._active():
            return None
        if self.db.kv_get("paused") == "1" or self.db.kv_get("boss_active") == "1":
            return None
        now = time.time()
        cd_until = float(self.db.kv_get("surprise_cooldown_until", "0") or 0)
        if now < cd_until:
            return None
        # session must be active: a command within the active window
        cmds = events.recent_commands(self.db, limit=5)
        if not cmds:
            return None
        last_at = max(c.get("at", 0) for c in cmds)
        win = config.get("surprise_active_window_minutes") * 60
        if now - last_at > win:
            return None
        # first roll no earlier than N minutes after session start
        sess_start = float(self.db.kv_get("session_start", "0") or 0)
        if sess_start == 0:
            self.db.kv_set("session_start", str(now))
            return None
        if now - sess_start < config.get("surprise_min_session_minutes") * 60:
            return None
        # throttle rolls to ~once / 10 min
        last_roll = float(self.db.kv_get("surprise_last_roll", "0") or 0)
        if now - last_roll < 600:
            return None
        self.db.kv_set("surprise_last_roll", str(now))
        if random.random() > config.get("surprise_chance"):
            return None
        ok, msg = self.start()
        return msg if ok else None

    # -- helpers ------------------------------------------------------
    def _legend(self, s: Surprise, params: dict) -> str:
        body = _render(s.brief, params)
        story = _render(s.story, params)
        out = f"«Детская неожиданность!» [{s.track}] — {s.title}\n"
        if story:
            out += story + "\n"
        out += body
        if s.hints:
            out += "\n(подсказки: sq hint surprise)"
        return out

    def _run_script(self, s: Surprise, rel: str | None, params: dict) -> None:
        if not rel:
            return
        script = s.dir / rel
        if not script.is_file():
            script = s.dir / "scripts" / Path(rel).name
        if not script.is_file():
            return
        env = dict(os.environ)
        env["SQ_HOME"] = os.path.expanduser("~")
        for k, v in params.items():
            env[f"SQ_SP_{k.upper()}"] = v
        interp = ["python3", "-I", str(script)] if script.suffix == ".py" else ["bash", str(script)]
        try:
            subprocess.run(interp, timeout=20, env=env)
        except (OSError, subprocess.SubprocessError):
            pass

    def codex_card(self, sid: str) -> str | None:
        s = self.pool.get(sid)
        if not s or not s.codex:
            return None
        card = s.dir / s.codex
        if not card.is_file():
            card = s.dir / "codex" / Path(s.codex).name
        return card.read_text() if card.is_file() else None
