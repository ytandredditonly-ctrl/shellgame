"""Build the read-only state snapshot the GUI consumes (GUI spec §9).

The GUI never mutates state; it renders this snapshot and re-fetches it when a
cheap `state_version` changes. Validator pass/pending dots are evaluated here
for the current level's available quests so the GUI can show live progress.
"""
from __future__ import annotations

from typing import Any

from .engine import Engine
from .validators import run_validator

ACTS = [{"act": 1, "levels": [0, 1, 2, 3, 4, 5]},
        {"act": 2, "levels": [6, 7, 8, 9]}]


def state_version(db) -> str:
    """Cheap change key — rebuild the full snapshot only when this changes."""
    p = db.profile()
    rows = db.conn.execute("SELECT MAX(id) m FROM event_log").fetchone()
    last_ev = rows["m"] if rows and rows["m"] is not None else 0
    opened = len(db.opened_commands())
    active = db.kv_get("boss_active", "0")
    surprise = "1" if db.kv_get("surprise_active") else "0"
    if not p:
        return f"noprofile:{last_ev}"
    return f"{p['level']}:{p['level_xp']}:{p['coins']}:{opened}:{p['boss_unlocked']}:{active}:{surprise}:{last_ev}"


def build(db, content) -> dict[str, Any]:
    eng = Engine(db, content)
    p = db.profile()
    if not p:
        return {"ready": False}
    level = eng.current_level()
    if not level:
        return {"ready": False}
    eng._ensure_level_quests(level)

    opened = db.opened_commands()
    targets = level.target_commands
    xp_req = eng.effective_xp_required(level)
    open_count = len(set(targets) & opened)

    # boss state
    if eng.boss_active():
        bstate = "in_fight"
    elif p["boss_unlocked"]:
        bstate = "unlocked"
    elif eng.boss_defeated(level.id):
        bstate = "defeated"
    else:
        bstate = "locked"
    phase_idx, phases_total = 0, 0
    if level.boss:
        phases_total = len(level.boss.phases)
        for i, ph in enumerate(level.boss.phases):
            if db.phase_status(level.boss.id, ph.id) == "done":
                phase_idx = i + 1
            else:
                break

    # quests with live validator dots
    cmds = __import__("sq.events", fromlist=["recent_commands"]).recent_commands(db)
    ctx = eng._context(level, cmds)
    done = db.done_quests()
    quests = []
    for q in level.quests.values():
        st = db.quest_status(q.id) or "available"
        if st == "done":
            status = "done"
            vals = [{"name": v.get("type"), "pass": True} for v in q.validators]
        elif all(dep in done for dep in q.requires_quests):
            status = "available"
            vals = [{"name": v.get("type"),
                     "pass": run_validator(ctx, v) == "pass"} for v in q.validators]
        else:
            status = "blocked"
            vals = [{"name": v.get("type"), "pass": False} for v in q.validators]
        quests.append({
            "id": q.id, "title": q.title, "type": q.type, "status": status,
            "blocked_by": [d for d in q.requires_quests if d not in done],
            "goal": q.brief, "validators": vals,
            "xp": q.xp, "coins": q.coins,
            "hints_total": len(q.hints), "hints_open": db.hints_opened(q.id),
            "next_hint_cost": _next_hint_cost(q, db),
        })

    codex = []
    for lvl in content.levels.values():
        for cmd in lvl.target_commands:
            card = _codex_path(lvl, cmd)
            if cmd in {c["tool"] for c in codex}:
                continue
            codex.append({"tool": cmd, "open": cmd in opened,
                          "level": lvl.id, "has_card": card is not None})

    return {
        "ready": True,
        "level": {"id": level.id, "name": level.name, "xp": p["level_xp"],
                  "xp_required": xp_req, "xp_required_raw": level.xp_required,
                  "commands_open": open_count, "commands_target": len(targets),
                  "command_threshold": level.command_threshold,
                  "story_intro": level.story_intro},
        "coins": p["coins"],
        "boss": {"state": bstate, "phase": phase_idx, "phases_total": phases_total,
                 "name": level.boss.name if level.boss else None,
                 "brief": level.boss.story_brief if level.boss else ""},
        "acts": ACTS,
        "current_level_index": level.id,
        "defeated_levels": [i for i in content.levels if eng.boss_defeated(i)],
        "commands": [{"name": t, "open": t in opened} for t in targets],
        "quests": quests,
        "codex": codex,
        "surprise_active": bool(db.kv_get("surprise_active")),
        "xp_conditions": {
            "xp_ok": p["level_xp"] >= xp_req,
            "commands_ok": (open_count / max(1, len(targets))) >= level.command_threshold,
        },
    }


def _next_hint_cost(q, db) -> int | None:
    from .content import HINT_PRICES
    opened = db.hints_opened(q.id)
    if opened >= len(q.hints):
        return None
    return HINT_PRICES[min(opened, len(HINT_PRICES) - 1)]


def _codex_path(level, tool):
    card = level.dir / "codex" / f"{tool}.md"
    return card if card.is_file() else None


def codex_card(content, tool: str) -> str | None:
    for lvl in content.levels.values():
        card = _codex_path(lvl, tool)
        if card:
            return card.read_text()
    return None


# Static sq-command reference for the manual's "Commands" tab (GUI spec §7.2).
COMMANDS_TABLE = [
    ("sq status", "Уровень, опыт, команды, монеты, статус босса", "sq status"),
    ("sq quests", "Список заданий уровня", "sq quests"),
    ("sq quest <id>", "Описание задания и его целей", "sq quest l4-q03"),
    ("sq check", "Принудительная проверка активных заданий", "sq check"),
    ("sq answer <text>", "Ответ для заданий с output_matches", "sq answer nightfall"),
    ("sq flag <value>", "Сдать флаг", "sq flag ARCHITECT-7731"),
    ("sq shop", "Магазин утилит текущего уровня", "sq shop"),
    ("sq buy <pkg>", "Купить и установить утилиту", "sq buy nmap"),
    ("sq hint <id>", "Купить следующую подсказку", "sq hint l4-q03"),
    ("sq codex [tool]", "Открытые утилиты или карточка одной", "sq codex ss"),
    ("sq boss start|resume|abort", "Управление боем с боссом", "sq boss start"),
    ("sq surprise [track]", "Ивент «Детская неожиданность»", "sq surprise crypto"),
    ("sq log", "История событий", "sq log"),
    ("sq pause | sq resume", "Выключить/включить отслеживание", "sq pause"),
    ("sq gui", "Открыть это окно-компаньон", "sq gui"),
]

HOWTO = [
    ("Уровни", "Игра линейна: уровень открывает набор утилит, задания учат ими пользоваться, босс проверяет связку."),
    ("Опыт (XP)", "Задания и первое применение команды дают опыт. Набери порог уровня — это одно из условий открытия босса."),
    ("Команды", "Используй целевые команды уровня успешно хотя бы раз — они «открываются» (XP + карточка в кодексе). Нужно открыть ≥80%."),
    ("Босс", "Когда опыт и команды добраны — босс открывается. Запусти бой: sq boss start. Победа поднимает уровень."),
    ("Монеты", "Тратятся в магазине (sq buy) на утилиты и на подсказки (sq hint). Опыт потратить нельзя."),
    ("Подсказки", "У задания 2–3 уровня подсказок: намёк → утилита → готовая команда. Купленная остаётся открытой."),
    ("Ивенты", "Иногда всплывает «Детская неожиданность» — короткая задачка. Реши её или сбрось: sq surprise drop."),
]
