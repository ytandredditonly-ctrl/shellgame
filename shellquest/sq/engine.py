"""Progression engine: quests, command opening, economy, boss, level-up.

Pure logic over the DB + content. The CLI and daemon both drive it; it owns
no I/O beyond the DB and the validator subprocess calls.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import content as C
from . import events
from .db import DB
from .validators import Context, run_validator

COMMAND_XP = 10
COMMAND_COINS = 5


def _all_content_packages(content: C.Content) -> list[str]:
    pkgs: set[str] = set()
    for lvl in content.levels.values():
        pkgs.update(lvl.unlock_packages)
        for item in lvl.shop:
            if item.get("package"):
                pkgs.add(item["package"])
    return sorted(pkgs)


@dataclass
class CheckResult:
    newly_done_quests: list[str]
    opened_commands: list[str]
    boss_unlocked: bool
    level_up: bool
    messages: list[str]


class Engine:
    def __init__(self, db: DB, content: C.Content):
        self.db = db
        self.content = content

    # -- profile helpers ----------------------------------------------
    @property
    def level_id(self) -> int:
        p = self.db.profile()
        return p["level"] if p else 0

    def current_level(self) -> C.Level | None:
        return self.content.level(self.level_id)

    def _ensure_level_quests(self, level: C.Level) -> None:
        for q in level.quests.values():
            self.db.ensure_quest(q.id, level.id)

    def _run_level_setup(self, level: C.Level) -> None:
        """Run a level's setup script (host-local playground). Best-effort."""
        import subprocess

        if not level.setup:
            return
        script = level.dir / level.setup
        if not script.is_file():
            script = level.dir / "scripts" / Path(level.setup).name
        if not script.is_file():
            return
        interp = (
            ["python3", "-I", str(script)]
            if script.suffix == ".py"
            else ["bash", str(script)]
        )
        try:
            subprocess.run(interp, timeout=60)
            self.db.log_change("level_setup", f"level {level.id}")
        except (OSError, subprocess.SubprocessError):
            pass

    # -- availability --------------------------------------------------
    def quest_available(self, q: C.Quest, done: set[str]) -> bool:
        return all(dep in done for dep in q.requires_quests)

    def available_quests(self) -> list[C.Quest]:
        level = self.current_level()
        if not level:
            return []
        done = self.db.done_quests()
        out = []
        for q in level.quests.values():
            if self.db.quest_status(q.id) == "done":
                continue
            if self.quest_available(q, done):
                out.append(q)
        return out

    # -- command opening ----------------------------------------------
    def _process_command_opens(self, level: C.Level, cmds: list[dict]) -> list[str]:
        opened_now: list[str] = []
        already = self.db.opened_commands()
        targets = set(level.target_commands)
        for ev in cmds:
            if ev.get("exit") != 0:
                continue
            # credit every name a line maps to (so `sudo useradd` opens both)
            for name in ev.get("names") or [ev.get("name")]:
                if (
                    name in targets
                    and name not in already
                    and name not in opened_now
                ):
                    if self.db.open_command(name):
                        opened_now.append(name)
                        self.db.add_xp_coins(COMMAND_XP, COMMAND_COINS)
                        self.db.log_event("command_opened", command=name)
                        events.emit("command_opened", command=name)
        return opened_now

    # -- context -------------------------------------------------------
    def _context(self, level: C.Level, cmds: list[dict], answer=None, flag=None) -> Context:
        import json as _json

        try:
            visited = _json.loads(self.db.kv_get("visited_dirs", "[]") or "[]")
        except ValueError:
            visited = []
        # Fold in the cwds observed on buffered command events too.
        visited += [c.get("cwd", "") for c in cmds if c.get("cwd")]
        return Context(
            db=self.db,
            content_dir=self.content.dir,
            scripts_dir=level.dir / "scripts",
            commands=cmds,
            cwd=self.db.kv_get("player_cwd", os.path.expanduser("~")) or "",
            visited=sorted(set(visited)),
            answer=answer,
            flag=flag,
            env=dict(os.environ),
        )

    # -- main check ----------------------------------------------------
    def check(self, answer: str | None = None, flag: str | None = None) -> CheckResult:
        events.drain_buffer(self.db)
        level = self.current_level()
        msgs: list[str] = []
        if not level:
            return CheckResult([], [], False, False, ["Нет контента для текущего уровня."])

        self._ensure_level_quests(level)
        cmds = events.recent_commands(self.db)

        opened = self._process_command_opens(level, cmds)
        for c in opened:
            msgs.append(f"Открыта команда: {c} (+{COMMAND_XP} XP, +{COMMAND_COINS} монет)")

        ctx = self._context(level, cmds, answer=answer, flag=flag)

        newly_done: list[str] = []
        done = self.db.done_quests()
        for q in level.quests.values():
            if self.db.quest_status(q.id) == "done":
                continue
            if not self.quest_available(q, done):
                continue
            results = [run_validator(ctx, v) for v in q.validators]
            if results and all(r == "pass" for r in results):
                self.db.complete_quest(q.id)
                self.db.add_xp_coins(q.xp, q.coins)
                self.db.log_event("quest_done", quest=q.id, xp=q.xp, coins=q.coins)
                events.emit("quest_done", quest=q.id)
                newly_done.append(q.id)
                done.add(q.id)
                msgs.append(
                    f"Задание пройдено: {q.title} (+{q.xp} XP, +{q.coins} монет)"
                )

        boss_unlocked, level_up = self._reconcile_boss_state(level, msgs)
        return CheckResult(newly_done, opened, boss_unlocked, level_up, msgs)

    # -- boss unlock condition (§8) -----------------------------------
    def command_progress(self, level: C.Level) -> tuple[int, int, float]:
        targets = set(level.target_commands)
        opened = len(self.db.opened_commands() & targets)
        total = len(targets) or 1
        return opened, len(targets), opened / total

    def available_xp(self, level: C.Level) -> int:
        """Max XP obtainable on this level: all quests + opening every target."""
        return sum(q.xp for q in level.quests.values()) + COMMAND_XP * len(
            level.target_commands
        )

    def effective_xp_required(self, level: C.Level) -> int:
        """Clamp an unreachable threshold down to what the level can give (§8)."""
        avail = self.available_xp(level)
        if level.xp_required > avail:
            key = f"xp_clamp_warned_{level.id}"
            if self.db.kv_get(key) != "1":
                self.db.log_event(
                    "xp_threshold_clamped",
                    level=level.id,
                    requested=level.xp_required,
                    effective=avail,
                )
                self.db.kv_set(key, "1")
            return avail
        return level.xp_required

    def boss_conditions_met(self, level: C.Level) -> bool:
        p = self.db.profile()
        if not p:
            return False
        _, _, frac = self.command_progress(level)
        return (
            p["level_xp"] >= self.effective_xp_required(level)
            and frac >= level.command_threshold
        )

    def boss_defeated(self, level_id: int) -> bool:
        return self.db.kv_get(f"boss_defeated_{level_id}") == "1"

    def _reconcile_boss_state(self, level: C.Level, msgs: list[str]) -> tuple[bool, bool]:
        p = self.db.profile()
        boss_unlocked = False
        if (
            level.boss
            and not p["boss_unlocked"]
            and not self.boss_defeated(level.id)
            and self.boss_conditions_met(level)
        ):
            self.db.set_profile(boss_unlocked=1)
            self.db.log_event("boss_unlocked", boss=level.boss.id)
            events.emit("boss_unlocked", boss=level.boss.id)
            msgs.append(f"⚔ Открыт босс уровня: {level.boss.name}! (sq boss start)")
            boss_unlocked = True
        return boss_unlocked, False

    # -- boss fight ----------------------------------------------------
    def boss_active(self) -> bool:
        return self.db.kv_get("boss_active") == "1"

    def _arena_compose(self, level: C.Level) -> str | None:
        """Content-relative path of the boss arena compose file, if any."""
        if not level.boss or not level.boss.arena:
            return None
        rel = level.dir / level.boss.arena
        try:
            return str(rel.relative_to(self.content.dir))
        except ValueError:
            return str(rel)

    def start_boss(self) -> tuple[bool, str]:
        level = self.current_level()
        if not level or not level.boss:
            return False, "У этого уровня нет босса."
        p = self.db.profile()
        if not p["boss_unlocked"]:
            return False, "Босс ещё не открыт. Набери опыт и открой команды уровня."
        notes = []
        compose = self._arena_compose(level)
        if compose:
            from . import helper

            res = helper.arena_up(compose)
            if res.reached and res.ok:
                notes.append("Арена поднята." + (" (dry-run)" if res.dry_run else ""))
            elif res.reached:
                notes.append(f"Арену поднять не удалось: {res.output[:120]}")
            else:
                notes.append("sq-helperd не запущен — арена не поднята "
                             "(фазы с контейнерами будут ждать).")
        self.db.kv_set("boss_active", "1")
        self.db.reset_boss(level.boss.id)
        self.db.log_event("boss_started", boss=level.boss.id)
        events.emit("boss_started", boss=level.boss.id)
        brief = level.boss.story_brief or f"Бой с боссом {level.boss.name} начат."
        if notes:
            brief += "\n" + "\n".join(notes)
        return True, brief

    def abort_boss(self) -> str:
        level = self.current_level()
        compose = self._arena_compose(level) if level else None
        if compose:
            from . import helper

            helper.arena_down(compose)
        if level and level.boss:
            self.db.reset_boss(level.boss.id)
        self.db.kv_set("boss_active", "0")
        self.db.log_event("boss_aborted")
        return "Бой прерван, арена снесена, прогресс фаз сброшен."

    def check_boss(self, answer=None, flag=None) -> CheckResult:
        events.drain_buffer(self.db)
        level = self.current_level()
        msgs: list[str] = []
        if not level or not level.boss:
            return CheckResult([], [], False, False, ["Нет активного босса."])
        if not self.boss_active():
            return CheckResult([], [], False, False, ["Бой не запущен (sq boss start)."])

        boss = level.boss
        cmds = events.recent_commands(self.db)
        ctx = self._context(level, cmds, answer=answer, flag=flag)

        # Phases are sequential: only check the first not-done phase.
        done_phase = None
        for ph in boss.phases:
            if self.db.phase_status(boss.id, ph.id) == "done":
                continue
            results = [run_validator(ctx, v) for v in ph.validators]
            if results and all(r == "pass" for r in results):
                self.db.set_phase(boss.id, ph.id, "done")
                self.db.log_event("boss_phase_done", boss=boss.id, phase=ph.id)
                msgs.append(f"Фаза пройдена: {ph.brief}")
                done_phase = ph.id
            break  # sequential — stop at first unfinished phase

        all_done = all(
            self.db.phase_status(boss.id, ph.id) == "done" for ph in boss.phases
        )
        level_up = False
        if all_done:
            msgs.append(f"★ Босс повержен: {boss.name}!")
            level_up = self._level_up(level, msgs)
        return CheckResult([], [], False, level_up, msgs)

    def _level_up(self, level: C.Level, msgs: list[str]) -> bool:
        self.db.kv_set("boss_active", "0")
        self.db.kv_set(f"boss_defeated_{level.id}", "1")
        self.db.set_profile(boss_unlocked=0)
        self.db.log_event("boss_defeated", boss=level.boss.id if level.boss else "")
        events.emit("boss_defeated", boss=level.boss.id if level.boss else "")

        # Arena is no longer needed after victory.
        compose = self._arena_compose(level)
        if compose:
            from . import helper

            helper.arena_down(compose)
        if level.story_outro:
            msgs.append(level.story_outro)

        next_id = level.id + 1
        nxt = self.content.level(next_id)
        if nxt is None:
            self.db.kv_set("game_complete", "1")
            msgs.append("Это был последний доступный уровень контента. Поздравляем!")
            self.db.log_event("game_complete")
            return True

        self.db.set_profile(level=next_id, level_xp=0, boss_unlocked=0)
        self.db.log_event("level_up", level=next_id)
        events.emit("level_up", level=next_id)
        self._ensure_level_quests(nxt)
        # Run the next level's setup (idempotent) and install its unlocked tools.
        if nxt.setup and self.db.kv_get(f"setup_done_{nxt.id}") != "1":
            self._run_level_setup(nxt)
            self.db.kv_set(f"setup_done_{nxt.id}", "1")
        if nxt.unlock_packages:
            from . import helper

            allow = _all_content_packages(self.content)
            installed = []
            for pkg in nxt.unlock_packages:
                r = helper.install_package(pkg, allow=allow)
                if r.ok:
                    installed.append(pkg + (" (dry-run)" if r.dry_run else ""))
            if installed:
                msgs.append("Установлены инструменты уровня: " + ", ".join(installed))
            elif not helper.available():
                msgs.append("Инструменты уровня поставит sq-helperd, когда он поднят: "
                            + ", ".join(nxt.unlock_packages))
        msgs.append(f"Уровень повышен до {next_id} — «{nxt.name}».")
        if nxt.story_intro:
            msgs.append(nxt.story_intro)
        return True

    # -- hints ---------------------------------------------------------
    def buy_hint(self, quest_id: str) -> tuple[bool, str]:
        level = self.current_level()
        if not level:
            return False, "Нет уровня."
        quest = level.quests.get(quest_id)
        phase = None
        if quest is None and level.boss:
            for ph in level.boss.phases:
                if ph.id == quest_id:
                    phase = ph
                    break
        hints = quest.hints if quest else (phase.hints if phase else [])
        if not hints:
            return False, f"У «{quest_id}» нет подсказок."

        opened = self.db.hints_opened(quest_id)
        if opened >= len(hints):
            return True, "\n".join(
                f"[{i + 1}] {h}" for i, h in enumerate(hints)
            )
        mult = (
            level.boss.hint_multiplier if (phase and level.boss) else 1.0
        )
        price = int(C.HINT_PRICES[min(opened, len(C.HINT_PRICES) - 1)] * mult)
        p = self.db.profile()
        if p["coins"] < price:
            return False, f"Не хватает монет: нужно {price}, есть {p['coins']}."
        self.db.spend_coins(price)
        self.db.buy_hint(quest_id, opened + 1)
        self.db.log_event("hint_bought", quest=quest_id, n=opened + 1, price=price)
        shown = "\n".join(f"[{i + 1}] {hints[i]}" for i in range(opened + 1))
        return True, f"(−{price} монет)\n{shown}"
