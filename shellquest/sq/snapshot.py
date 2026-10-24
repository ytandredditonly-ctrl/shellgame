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
    track = db.kv_get("track", "main")
    return f"{track}:{p['level']}:{p['level_xp']}:{p['coins']}:{opened}:{p['boss_unlocked']}:{active}:{surprise}:{last_ev}"


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
                  "story_intro": level.story_intro,
                  "is_dlc": level.is_dlc, "dlc_id": level.dlc_id},
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
        "track": eng.active_track(),
        "dlc_available": eng.dlc_available(),
        "dlc": [
            {"dlc_id": m.dlc_id, "name": m.name,
             "state": ("current" if (eng.active_track() == "dlc" and m.id == level.id)
                       else "defeated" if eng.boss_defeated(m.id)
                       else "unlocked" if eng.dlc_module_unlocked(m)
                       else "locked")}
            for m in content.dlc_modules()
        ],
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
    ("sq status", "Где я сейчас: уровень, опыт, команды, монеты, статус босса", "sq status"),
    ("sq quests", "Список заданий текущего уровня или модуля", "sq quests"),
    ("sq quest <id>", "Подробно про одно задание: цель, награда, подсказки", "sq quest l4-q03"),
    ("sq check", "Проверить задания прямо сейчас (обычно не нужно — идёт само)", "sq check"),
    ("sq answer <текст>", "Сдать текстовый ответ на задание", "sq answer nightfall"),
    ("sq flag <значение>", "Сдать флаг (секрет, который нужно добыть)", "sq flag ARCHITECT-7731"),
    ("sq shop", "Что можно купить на этом уровне/модуле", "sq shop"),
    ("sq buy <пакет>", "Купить и установить утилиту за монеты", "sq buy nmap"),
    ("sq hint <id>", "Купить следующую подсказку к заданию или фазе", "sq hint l4-q03"),
    ("sq codex [утилита]", "Список открытых утилит или карточка одной из них", "sq codex ss"),
    ("sq boss start|resume|abort", "Начать бой с боссом / продолжить / прервать", "sq boss start"),
    ("sq dlc", "DLC «Арсенал»: список модулей (открывается после босса ур.5)", "sq dlc"),
    ("sq dlc start <м> | leave", "Войти в модуль DLC / вернуться в основную игру", "sq dlc start d1"),
    ("sq surprise [трек]", "Запустить ивент-сюрприз: crypto | net | linux | drop", "sq surprise crypto"),
    ("sq log", "История событий игры", "sq log"),
    ("sq pause | sq resume", "Пауза/возобновление слежения за командами", "sq pause"),
    ("sq gui", "Открыть это окно-компаньон", "sq gui"),
]

HOWTO = [
    ("Что это такое",
     "shellquest превращает изучение Kali Linux в игру. Ты — новый оператор "
     "заброшенной машины. Игра смотрит на РЕАЛЬНОЕ состояние системы: опыт даётся "
     "за настоящий результат (создан файл, успешно выполнена команда, сдан флаг), "
     "а не за «правильный» текст. Перерывы не наказываются — прогресс сохраняется."),
    ("С чего начать",
     "1) Открой «Текущие задания» справа. 2) Возьми верхнее задание и прочитай цель. "
     "3) Сделай то, что просят, в терминале. 4) Нажми «Проверить» (или команду sq check). "
     "Готово — карточка задания станет зелёной сама."),
    ("Как сдавать ответы",
     "Если в цели написано «sq answer <…>» или «sq flag <…>» — впиши значение в поле "
     "вверху панели заданий и нажми «Ответ» или «Флаг». Можно и в терминале: "
     "sq answer <текст>  либо  sq flag <значение>."),
    ("Опыт (XP) и порог",
     "За задания и за первое успешное применение новой команды начисляется опыт. "
     "Кольцо слева показывает, сколько XP набрано и сколько нужно до босса. "
     "Порог XP — одно из двух условий, чтобы открыть босса."),
    ("Команды уровня",
     "У каждого уровня есть свой набор команд (чипы «Открытые команды»). Примени "
     "команду успешно хотя бы раз — она «откроется»: +опыт и карточка в Кодексе. "
     "Нужно открыть не меньше 80% — это второе условие босса."),
    ("Босс",
     "Когда оба условия выполнены (опыт ≥ порога и команды ≥ 80%), значок «Босс» "
     "вверху загорается. Нажми его, чтобы начать бой. Босс идёт по фазам; пройди "
     "все — и уровень повысится. Фазы проверяются теми же «Проверить»/ответом/флагом."),
    ("Монеты и магазин",
     "Монеты копятся вместе с опытом и не сгорают. Трать их в магазине на новые "
     "утилиты (sq buy <пакет>) и на подсказки. Опытом платить нельзя."),
    ("Подсказки",
     "У задания есть 2–3 подсказки по нарастающей: намёк → какая утилита → готовая "
     "команда. Кнопка «Подсказка» покупает следующую за монеты; купленная остаётся "
     "открытой навсегда."),
    ("DLC «Арсенал»",
     "После победы над боссом уровня 5 открывается второй трек — курс из 10 модулей "
     "по инструментам ИБ (nmap, Wireshark, Burp, Metasploit, John/Hashcat, Hydra, "
     "sqlmap, Aircrack, Nikto/gobuster/ffuf, tcpdump) и финальный экзамен. Полоса "
     "«DLC Арсенал» слева: нажми открытый модуль, чтобы войти, и «← в основную игру», "
     "чтобы вернуться. У основной игры и DLC свои прогресс и опыт — они не мешают друг другу."),
    ("Кнопки реально работают",
     "Кнопки в окне не копируют команды, а сразу выполняют их в игре: «Проверить», "
     "«Подсказка», ответ/флаг, запуск босса, вход в модуль DLC. Вкладка «Команды» "
     "в мануале — это справочник: там кнопки копируют пример в буфер обмена."),
    ("Цели — только учебные",
     "Все атаки в DLC идут ТОЛЬКО по локальным учебным контейнерам (сеть без выхода "
     "наружу). Ничего не направлено на реальные или чужие машины."),
    ("Ивенты",
     "Иногда всплывает «Детская неожиданность» — короткая задачка-сюрприз. Реши её "
     "ради бонуса или сбрось без потерь: sq surprise drop."),
]
