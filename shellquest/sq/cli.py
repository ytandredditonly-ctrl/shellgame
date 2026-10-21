"""`sq` command-line interface (argparse — no third-party deps)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

from . import config as CFG
from . import content as C
from . import events, paths
from .db import DB
from .engine import Engine
from .surprises import SurpriseEngine

# ---- ANSI helpers (muted when not a tty or SQ_NO_COLOR set) ----------
_TTY = sys.stdout.isatty() and not os.environ.get("SQ_NO_COLOR")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _TTY else s


def bold(s): return _c("1", s)
def dim(s): return _c("2", s)
def green(s): return _c("32", s)
def yellow(s): return _c("33", s)
def cyan(s): return _c("36", s)
def red(s): return _c("31", s)


def notify(title: str, body: str) -> None:
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", title, body], timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass


def _load() -> tuple[DB, Engine]:
    db = DB()
    content = C.Content()
    return db, Engine(db, content)


def _print_messages(msgs: list[str], quiet: bool = False) -> None:
    for m in msgs:
        print(green("  ✓ ") + m if "пройдено" in m or "Открыт" in m else "  " + m)
    if msgs and not quiet:
        head = next((m for m in msgs if "повержен" in m or "Открыт босс" in m), None)
        if head:
            notify("shellquest", head)


# ---- commands --------------------------------------------------------
def cmd_init(args) -> int:
    paths.ensure_dirs()
    db, eng = _load()
    db.init_profile()
    db.kv_set("paused", "0")
    level = eng.current_level()
    if level is None:
        print(red("Контент не найден в "), paths.CONTENT_DIR)
        return 1
    eng._ensure_level_quests(level)

    # Run the level setup script once (idempotent in the script itself).
    if level.setup and db.kv_get(f"setup_done_{level.id}") != "1":
        _run_content_script(level, level.setup)
        db.kv_set(f"setup_done_{level.id}", "1")
        db.log_change("level_setup", f"level {level.id}: {level.setup}")

    print(bold("── shellquest ──"))
    print(level.story_intro or "")
    print()
    print("Профиль создан. Хук отслеживает команды в вашей оболочке.")
    print(dim("Рекомендация: сделайте снапшот системы (Timeshift) перед игрой."))
    print()
    print("Дальше: " + cyan("sq status") + "  ·  " + cyan("sq quests"))
    db.log_event("init")
    return 0


def _run_content_script(level: C.Level, rel: str) -> None:
    from pathlib import Path

    script = level.dir / rel
    if not script.is_file():
        # allow "scripts/foo.sh" or bare name
        script = level.dir / "scripts" / Path(rel).name
    if not script.is_file():
        return
    interp = ["python3", "-I", str(script)] if script.suffix == ".py" else ["bash", str(script)]
    try:
        subprocess.run(interp, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def cmd_status(args) -> int:
    db, eng = _load()
    p = db.profile()
    if not p:
        print("Сначала запустите " + cyan("sq init"))
        return 1
    level = eng.current_level()
    if not level:
        print("Нет контента для уровня", eng.level_id)
        return 1
    opened, total, frac = eng.command_progress(level)
    boss_state = "открыт ⚔" if p["boss_unlocked"] else "закрыт"
    if eng.boss_defeated(level.id):
        boss_state = "повержен ✓"
    if eng.boss_active():
        boss_state = "идёт бой ⚔"
    if db.kv_get("game_complete") == "1":
        boss_state += "  ·  контент пройден 🏁"

    xp_req = eng.effective_xp_required(level)
    bar = _bar(p["level_xp"], xp_req)
    print(bold(f"Уровень {level.id} — «{level.name}»"))
    note = dim(f" (порог снижен с {level.xp_required})") if xp_req != level.xp_required else ""
    print(f"  Опыт:    {p['level_xp']}/{xp_req}  {bar}{note}")
    print(f"  Команды: {opened}/{total} открыто ({int(frac*100)}%, порог {int(level.command_threshold*100)}%)")
    print(f"  Монеты:  {p['coins']}")
    print(f"  Босс:    {boss_state}")
    if p["boss_unlocked"] and not eng.boss_active():
        print(cyan("  → sq boss start"))
    return 0


def _bar(cur: int, total: int, width: int = 10) -> str:
    if total <= 0:
        total = 1
    filled = min(width, int(width * cur / total))
    return _c("36", "▰" * filled) + dim("▱" * (width - filled))


def cmd_quests(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    if not level:
        print("Нет уровня.")
        return 1
    eng._ensure_level_quests(level)
    done = db.done_quests()
    print(bold(f"Задания уровня {level.id} — «{level.name}»"))
    for q in level.quests.values():
        if db.quest_status(q.id) == "done":
            tag = green("[✓]")
        elif eng.quest_available(q, done):
            tag = yellow("[ ]")
        else:
            dep = ", ".join(q.requires_quests)
            tag = dim(f"[·] (нужно: {dep})")
        print(f"  {tag} {bold(q.id)}  {q.title}")
    print(dim("\nПодробнее: sq quest <id>"))
    return 0


def cmd_quest(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    q = level.quests.get(args.id) if level else None
    if not q:
        print(red(f"Задание {args.id} не найдено на текущем уровне."))
        return 1
    status = db.quest_status(q.id) or "available"
    print(bold(f"{q.id} — {q.title}") + dim(f"  [{q.type}]"))
    print(f"\n{q.brief}\n")
    if q.requires_quests:
        print(dim("Зависит от: " + ", ".join(q.requires_quests)))
    print(dim(f"Награда: {q.xp} XP · {q.coins} монет"))
    print(dim(f"Статус: {status}"))
    opened = db.hints_opened(q.id)
    if q.hints:
        print(f"\nПодсказки: открыто {opened}/{len(q.hints)}  (sq hint {q.id})")
        for i in range(opened):
            print("  " + dim(f"[{i+1}] {q.hints[i]}"))
    return 0


def cmd_check(args) -> int:
    db, eng = _load()
    if db.kv_get("paused") == "1":
        print(dim("Игра на паузе (sq resume)."))
        return 0
    if eng.boss_active():
        res = eng.check_boss()
    else:
        res = eng.check()
    if not res.messages:
        print(dim("Изменений нет. Выполняйте цели и повторите sq check."))
    else:
        _print_messages(res.messages, quiet=args.quiet)
    return 0


def _try_surprise(db, eng, *, answer=None, flag=None):
    """Route an answer/flag to an active surprise first. Returns msg or None."""
    se = SurpriseEngine(db, eng.content)
    if not se.active_id():
        return None
    ok, msg = se.submit(answer=answer, flag=flag)
    if ok:
        card = None
        import re
        m = re.search(r"кодексе: (\S+)", msg)
        if m:
            card = se.codex_card(m.group(1))
        return msg + (("\n\n" + card) if card else "")
    return None  # fall through to quests if the surprise rejected it


def cmd_answer(args) -> int:
    db, eng = _load()
    text = " ".join(args.text)
    smsg = _try_surprise(db, eng, answer=text)
    if smsg:
        print(green("! ") + smsg)
        return 0
    if eng.boss_active():
        res = eng.check_boss(answer=text)
    else:
        res = eng.check(answer=text)
    if res.messages:
        _print_messages(res.messages, quiet=args.quiet)
    else:
        print(red("Ответ не подошёл ни к одному активному заданию."))
    return 0


def cmd_flag(args) -> int:
    db, eng = _load()
    text = args.value
    smsg = _try_surprise(db, eng, flag=text)
    if smsg:
        print(green("! ") + smsg)
        return 0
    if eng.boss_active():
        res = eng.check_boss(flag=text)
    else:
        res = eng.check(flag=text)
    if res.messages:
        _print_messages(res.messages, quiet=args.quiet)
    else:
        print(red("Флаг неверный."))
    return 0


def cmd_shop(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    if not level:
        return 1
    p = db.profile()
    print(bold(f"Магазин уровня {level.id}  ·  монет: {p['coins']}"))
    if not level.shop:
        print(dim("  Пусто — на этом уровне всё нужное уже базовое."))
        return 0
    installed = set()
    for item in level.shop:
        pkg = item["package"]
        have = _pkg_installed(pkg)
        mark = green("✓ ") if have else f"{item.get('price', 0)}м "
        print(f"  {mark}{bold(item.get('name', pkg))} — {item.get('desc','')}")
    print(dim("\nКупить: sq buy <пакет>"))
    return 0


def _pkg_installed(pkg: str) -> bool:
    try:
        return subprocess.run(
            ["dpkg", "-s", pkg], capture_output=True, timeout=5
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def cmd_buy(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    item = next(
        (i for i in (level.shop if level else []) if i.get("package") == args.util or i.get("name") == args.util),
        None,
    )
    if not item:
        print(red(f"В магазине уровня нет «{args.util}»."))
        return 1
    pkg = item["package"]
    price = int(item.get("price", 0))
    if _pkg_installed(pkg):
        print(dim("Уже установлено."))
        return 0
    p = db.profile()
    if p["coins"] < price:
        print(red(f"Не хватает монет: нужно {price}, есть {p['coins']}."))
        return 1
    # Install is delegated to sq-helperd (§5/§12). Coins are only spent once we
    # know the install succeeded (or at least reached the helper in dry-run).
    from . import helper

    allow = _package_allowlist(eng)
    res = helper.install_package(pkg, allow=allow)
    if not res.reached:
        # Helper not running: record intent, keep coins, show the manual path.
        print(yellow("sq-helperd не запущен — установка отложена."))
        print(dim(f"Запусти помощник (systemctl --user start sq-helperd) или вручную: "
                  f"sudo apt-get install -y {pkg}"))
        print(dim("Монеты не списаны; повтори sq buy, когда помощник поднят."))
        return 1
    if not res.ok:
        print(red(f"Помощник отклонил установку: {res.output[:200]}"))
        return 1
    db.spend_coins(price)
    db.log_event("buy", package=pkg, price=price, dry_run=res.dry_run)
    tag = " (dry-run)" if res.dry_run else ""
    print(green(f"Куплено и установлено: {pkg} (−{price} монет){tag}."))
    return 0


def _package_allowlist(eng) -> list[str]:
    """Every package the content legitimately installs (shop + unlocks)."""
    pkgs: set[str] = set()
    for lvl in eng.content.levels.values():
        pkgs.update(lvl.unlock_packages)
        for item in lvl.shop:
            if item.get("package"):
                pkgs.add(item["package"])
    return sorted(pkgs)


def cmd_hint(args) -> int:
    db, eng = _load()
    if not args.id:
        print("Укажите id задания или фазы: sq hint <id>  (или sq hint surprise)")
        return 1
    if args.id == "surprise":
        se = SurpriseEngine(db, eng.content)
        ok, msg = se.buy_hint(eng)
        print(msg if ok else red(msg))
        return 0 if ok else 1
    ok, msg = eng.buy_hint(args.id)
    print(msg if ok else red(msg))
    return 0 if ok else 1


def cmd_surprise(args) -> int:
    db, eng = _load()
    se = SurpriseEngine(db, eng.content)
    sub = args.track
    if sub == "status":
        print(se.status())
        return 0
    if sub == "drop":
        print(se.drop())
        return 0
    track = sub if sub in ("crypto", "net", "linux") else None
    if se.active_id():
        print(dim("Ивент уже идёт:\n") + se.status())
        return 0
    ok, msg = se.start(track)
    if ok:
        print(bold("! ") + msg)
        notify("Детская неожиданность!", msg.splitlines()[0])
    else:
        print(dim(msg))
    return 0 if ok else 1


def cmd_codex(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    opened = db.opened_commands()
    if not args.util:
        print(bold("Открытые команды:"))
        print("  " + ", ".join(sorted(opened)) if opened else dim("  пока нет"))
        print(dim("\nКарточка: sq codex <команда>"))
        return 0
    # Surprise codex cards (solved events) are addressed by their sp-* id.
    if args.util.startswith("sp-"):
        se = SurpriseEngine(db, eng.content)
        card = se.codex_card(args.util)
        if card:
            print(card)
            return 0
        print(red(f"Карточка-разбор «{args.util}» недоступна (ивент не решён?)."))
        return 1
    if args.util not in opened:
        print(red(f"Команда «{args.util}» ещё не открыта."))
        return 1
    # Look for a codex card across all levels.
    for lvl in eng.content.levels.values():
        card = lvl.dir / "codex" / f"{args.util}.md"
        if card.is_file():
            print(card.read_text())
            return 0
    print(dim(f"Карточка для {args.util} ещё не написана. man {args.util}"))
    return 0


def cmd_boss(args) -> int:
    db, eng = _load()
    level = eng.current_level()
    if not level or not level.boss:
        print("У этого уровня нет босса.")
        return 1
    boss = level.boss
    if args.action == "start":
        if eng.boss_active():
            print(dim("Бой уже идёт. sq boss resume / abort"))
            return 0
        ok, msg = eng.start_boss()
        if not ok:
            print(red(msg))
            return 1
        print(bold(f"⚔ {boss.name}"))
        print("\n" + msg + "\n")
        _show_phases(db, boss, eng)
        notify("shellquest — босс", boss.name)
        return 0
    if args.action == "resume":
        if not eng.boss_active():
            print("Бой не запущен. sq boss start")
            return 1
        print(bold(f"⚔ {boss.name} — продолжение"))
        _show_phases(db, boss, eng)
        return 0
    if args.action == "abort":
        print(eng.abort_boss())
        return 0
    return 1


def _show_phases(db, boss, eng) -> None:
    for i, ph in enumerate(boss.phases, 1):
        st = db.phase_status(boss.id, ph.id)
        done = st == "done"
        # current phase = first not-done
        tag = green("✓") if done else "▶"
        if done:
            print(f"  {tag} Фаза {i}: {dim(ph.brief)}")
        else:
            print(f"  {tag} {bold(f'Фаза {i}')}: {ph.brief}")
            if ph.hints:
                print(dim(f"      подсказки: sq hint {ph.id}"))
            break
    print(dim("\nПроверка: sq check  ·  ответ: sq answer  ·  флаг: sq flag"))


def cmd_log(args) -> int:
    db, _ = _load()
    rows = db.events(limit=args.n)
    for r in reversed(rows):
        ts = datetime.fromtimestamp(r["at"]).strftime("%m-%d %H:%M")
        payload = json.loads(r["payload"])
        kind = r["kind"]
        if kind == "command":
            continue  # too noisy for the log view
        detail = payload.get("quest") or payload.get("command") or payload.get("boss") or payload.get("level") or ""
        print(f"{dim(ts)}  {bold(kind):<22} {detail}")
    return 0


def cmd_pause(args) -> int:
    db, _ = _load()
    db.kv_set("paused", "1")
    print(yellow("Отслеживание на паузе. Команды не учитываются. sq resume — продолжить."))
    return 0


def cmd_resume(args) -> int:
    db, _ = _load()
    db.kv_set("paused", "0")
    print(green("Отслеживание возобновлено."))
    return 0


def cmd_hook(args) -> int:
    """Internal: called by the zsh hook after each command. Fast & silent."""
    db = DB()
    if db.kv_get("paused") == "1":
        return 0
    cwd = args.cwd or os.getcwd()
    events.append_event(args.cmd or "", args.exit, cwd, args.dur)
    db.kv_set("player_cwd", cwd)
    # Track session start for the surprise scheduler (reset after a long gap).
    import time as _t
    now = _t.time()
    last = float(db.kv_get("last_cmd_at", "0") or 0)
    if now - last > 1800:  # >30 min idle -> new session
        db.kv_set("session_start", str(now))
    db.kv_set("last_cmd_at", str(now))
    # Keep a small set of visited dirs for history-based validators.
    try:
        visited = json.loads(db.kv_get("visited_dirs", "[]") or "[]")
    except ValueError:
        visited = []
    if cwd not in visited:
        visited.append(cwd)
        db.kv_set("visited_dirs", json.dumps(visited[-200:]))
    return 0


def cmd_prompt(args) -> int:
    """Internal: compact prompt indicator, must be cheap (§9)."""
    try:
        db = DB()
        p = db.profile()
        if not p:
            return 0
        content = C.Content()
        eng = Engine(db, content)
        level = eng.current_level()
        if not level:
            return 0
        opened, total, frac = eng.command_progress(level)
        filled = int(5 * p["level_xp"] / max(1, level.xp_required))
        bar = "▰" * min(5, filled) + "▱" * (5 - min(5, filled))
        boss = " ⚔" if p["boss_unlocked"] else ""
        surprise = " !" if db.kv_get("surprise_active") else ""
        sys.stdout.write(f"[L{level.id} {bar} {int(frac*100)}%{boss}{surprise}]")
    except Exception:
        pass
    return 0


def cmd_config(args) -> int:
    CFG.write_default()
    cfg = CFG.load(force=True)
    if args.action == "list" or (args.action is None):
        for k in sorted(cfg):
            print(f"  {k} = {cfg[k]}")
        print(dim(f"\nФайл: {paths.CONFIG_PATH}"))
        return 0
    if args.action == "get":
        print(cfg.get(args.key))
        return 0
    if args.action == "set":
        if args.key not in CFG.DEFAULTS:
            print(red(f"Неизвестный ключ: {args.key}"))
            return 1
        import yaml as _y
        data = {}
        if paths.CONFIG_PATH.is_file():
            data = _y.safe_load(paths.CONFIG_PATH.read_text()) or {}
        # coerce to the default's type
        default = CFG.DEFAULTS[args.key]
        val: object = args.value
        if isinstance(default, bool):
            val = str(args.value).lower() in ("1", "true", "yes", "on")
        elif isinstance(default, int):
            val = int(args.value)
        elif isinstance(default, float):
            val = float(args.value)
        data[args.key] = val
        paths.CONFIG_PATH.write_text(_y.safe_dump(data, sort_keys=True, allow_unicode=True))
        print(green(f"{args.key} = {val}"))
        return 0
    return 1


def cmd_helper(args) -> int:
    from . import helper
    r = helper.status()
    if not r.reached:
        print(red("sq-helperd не запущен."))
        print(dim("Запуск (root): sudo sq-helperd   или   systemctl --user ... (см. README)"))
        return 1
    print(green("sq-helperd доступен."))
    print(dim("  " + r.output))
    return 0


def cmd_resetup(args) -> int:
    """Re-run the current level's setup (restore marker processes / files).

    Safe to run any time: level setup scripts are idempotent. Handy after a
    reboot (userspace markers don't survive) or if you killed/removed something
    the level needs.
    """
    db, eng = _load()
    level = eng.current_level()
    if not level:
        print(red("Нет активного уровня."))
        return 1
    if not level.setup:
        print(dim(f"У уровня {level.id} нет окружения для восстановления."))
        return 0
    eng._run_level_setup(level)
    db.kv_set(f"setup_done_{level.id}", "1")
    print(green(f"Окружение уровня {level.id} восстановлено."))
    print(dim("Если задание ждало процесс/файл — повтори sq check."))
    return 0


def cmd_gui(args) -> int:
    from . import gui
    return gui.run(port=args.port, open_browser=not args.no_browser)


def cmd_uninstall(args) -> int:
    db, eng = _load()
    print(yellow("Откат изменений shellquest (§12)…"))
    for lvl in eng.content.levels.values():
        if lvl.teardown:
            _run_content_script(lvl, lvl.teardown)
    # Remove game data (keeps installed apt packages unless --purge handled by helper)
    print(dim("Выполнены teardown-скрипты уровней."))
    print(dim(f"Данные игры: {paths.DATA_DIR} (удалите вручную, если нужно)."))
    print("Снимите хук: удалите строку source .../sq-hook.zsh из ~/.zshrc")
    db.log_event("uninstall")
    return 0


# ---- parser ----------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sq", description="shellquest — Kali as an RPG")
    p.add_argument("--quiet", action="store_true", help="подавить терминальные уведомления")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("init", help="первый запуск").set_defaults(fn=cmd_init)
    sub.add_parser("status", help="прогресс уровня").set_defaults(fn=cmd_status)
    sub.add_parser("quests", help="список заданий").set_defaults(fn=cmd_quests)

    q = sub.add_parser("quest", help="описание задания"); q.add_argument("id"); q.set_defaults(fn=cmd_quest)
    sub.add_parser("check", help="проверить активные задания").set_defaults(fn=cmd_check)

    a = sub.add_parser("answer", help="ответ для output_matches"); a.add_argument("text", nargs="+"); a.set_defaults(fn=cmd_answer)
    f = sub.add_parser("flag", help="сдать флаг"); f.add_argument("value"); f.set_defaults(fn=cmd_flag)

    sub.add_parser("shop", help="магазин утилит").set_defaults(fn=cmd_shop)
    b = sub.add_parser("buy", help="купить утилиту"); b.add_argument("util"); b.set_defaults(fn=cmd_buy)
    h = sub.add_parser("hint", help="подсказка"); h.add_argument("id", nargs="?"); h.set_defaults(fn=cmd_hint)
    cx = sub.add_parser("codex", help="кодекс утилит"); cx.add_argument("util", nargs="?"); cx.set_defaults(fn=cmd_codex)

    bo = sub.add_parser("boss", help="управление боем"); bo.add_argument("action", choices=["start", "resume", "abort"]); bo.set_defaults(fn=cmd_boss)

    sp = sub.add_parser("surprise", help="ивент «Детская неожиданность»")
    sp.add_argument("track", nargs="?", help="crypto|net|linux | status | drop")
    sp.set_defaults(fn=cmd_surprise)

    cf = sub.add_parser("config", help="настройки игры")
    cf.add_argument("action", nargs="?", choices=["list", "get", "set"])
    cf.add_argument("key", nargs="?"); cf.add_argument("value", nargs="?")
    cf.set_defaults(fn=cmd_config)

    sub.add_parser("helper", help="статус sq-helperd").set_defaults(fn=cmd_helper)
    sub.add_parser("resetup", help="восстановить окружение уровня (процессы/файлы)").set_defaults(fn=cmd_resetup)

    g = sub.add_parser("gui", help="окно-компаньон (read-only)")
    g.add_argument("--port", type=int, default=8777)
    g.add_argument("--no-browser", action="store_true", help="не открывать браузер")
    g.set_defaults(fn=cmd_gui)

    lg = sub.add_parser("log", help="журнал событий"); lg.add_argument("-n", type=int, default=50); lg.set_defaults(fn=cmd_log)
    sub.add_parser("pause", help="пауза отслеживания").set_defaults(fn=cmd_pause)
    sub.add_parser("resume", help="продолжить отслеживание").set_defaults(fn=cmd_resume)
    sub.add_parser("uninstall", help="откатить изменения").set_defaults(fn=cmd_uninstall)

    hk = sub.add_parser("_hook", help=argparse.SUPPRESS)
    hk.add_argument("--cmd", default=""); hk.add_argument("--exit", type=int, default=0)
    hk.add_argument("--cwd", default=""); hk.add_argument("--dur", type=int, default=0)
    hk.set_defaults(fn=cmd_hook)
    sub.add_parser("_prompt", help=argparse.SUPPRESS).set_defaults(fn=cmd_prompt)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
