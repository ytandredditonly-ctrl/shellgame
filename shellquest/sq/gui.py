"""`sq gui` — the companion window (GUI spec).

A tiny local web server (stdlib only) serves a dark single-page app on
127.0.0.1 and pushes live state over Server-Sent Events. The page renders the
snapshot from `sq.snapshot`.

The game controls act for real: `POST /api/action` runs a small, fixed
whitelist of game operations in-process (check, boss, hints, buy, DLC switch,
surprise, answer/flag) — the same engine calls the `sq` CLI makes, no shell, no
arbitrary commands. It is guarded against cross-site/DNS-rebind calls (localhost
Host + a required `X-SQ-GUI` header a browser only sends same-origin). The
reference "Commands" table still copies examples to the clipboard.

Routes:
  GET  /                the SPA
  GET  /api/state       one state snapshot (JSON)
  GET  /api/stream      SSE; pushes the snapshot whenever state_version changes
  GET  /api/codex?tool= a codex card (markdown) for one tool
  GET  /api/manual      commands table + how-to (JSON)
  POST /api/action      run one whitelisted game action (JSON {action, args})
"""
from __future__ import annotations

import json
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import content as C
from . import snapshot
from .db import DB

WEBUI = Path(__file__).resolve().parent / "webui"
_CONTENT: C.Content | None = None


def _content() -> C.Content:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = C.Content()
    return _CONTENT


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._serve_file("index.html", "text/html; charset=utf-8")
            elif u.path == "/app.js":
                self._serve_file("app.js", "application/javascript; charset=utf-8")
            elif u.path == "/app.css":
                self._serve_file("app.css", "text/css; charset=utf-8")
            elif u.path == "/api/state":
                with _db() as db:
                    self._json(snapshot.build(db, _content()))
            elif u.path == "/api/manual":
                self._json({"commands": snapshot.COMMANDS_TABLE, "howto": snapshot.HOWTO})
            elif u.path == "/api/codex":
                tool = parse_qs(u.query).get("tool", [""])[0]
                card = snapshot.codex_card(_content(), tool)
                self._json({"tool": tool, "card": card})
            elif u.path == "/api/stream":
                self._stream()
            else:
                self._send(404, b"not found")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # never 500 the GUI into a stack trace
            try:
                self._json({"error": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/action":
            self._send(404, b"not found")
            return
        # CSRF / DNS-rebind guard: only genuine same-origin localhost calls.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host not in ("127.0.0.1", "localhost", "[::1]"):
            self._json({"ok": False, "message": "forbidden host"}, 403)
            return
        if self.headers.get("X-SQ-GUI") != "1":
            self._json({"ok": False, "message": "missing X-SQ-GUI header"}, 403)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except (ValueError, json.JSONDecodeError):
            self._json({"ok": False, "message": "bad request"}, 400)
            return
        action = str(data.get("action", ""))
        args = data.get("args") or {}
        try:
            with _db() as db:
                if not db.profile():
                    self._json({"ok": False, "message": "Игра не запущена (sq init)."})
                    return
                ok, msg = _do_action(db, action, args)
            self._json({"ok": bool(ok), "message": msg})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._json({"ok": False, "message": str(e)}, 500)

    def _serve_file(self, name, ctype):
        f = WEBUI / name
        if not f.is_file():
            self._send(404, b"missing asset")
            return
        self._send(200, f.read_bytes(), ctype)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_ver = None
        last_beat = 0.0
        while True:
            try:
                with _db() as db:
                    ver = snapshot.state_version(db)
                    if ver != last_ver:
                        last_ver = ver
                        snap = snapshot.build(db, _content())
                        payload = json.dumps(snap, ensure_ascii=False)
                        self.wfile.write(f"event: state\ndata: {payload}\n\n".encode())
                        self.wfile.flush()
                now = time.time()
                if now - last_beat > 15:
                    last_beat = now
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                break

    def log_message(self, *a):
        pass


# -- action dispatch (the GUI's write path) ---------------------------
#
# A fixed whitelist of game operations, each mapping to the very same engine
# call the `sq` CLI uses. No shell, no arbitrary commands, args validated.
def _do_action(db, action: str, args: dict):
    from .engine import Engine, _all_content_packages
    from .surprises import SurpriseEngine

    eng = Engine(db, _content())

    if action == "check":
        res = eng.check_boss() if eng.boss_active() else eng.check()
        return True, ("\n".join(res.messages) if res.messages
                      else "Изменений нет. Выполни цель и проверь снова.")

    if action == "boss_start":
        return eng.start_boss()
    if action == "boss_abort":
        return True, eng.abort_boss()

    if action == "hint":
        return eng.buy_hint(str(args.get("id", "")))

    if action == "buy":
        return _gui_buy(db, eng, str(args.get("pkg", "")), _all_content_packages)

    if action == "dlc_start":
        return _gui_dlc_start(db, eng, str(args.get("module", "")))
    if action == "dlc_leave":
        if eng.active_track() != "dlc":
            return True, "Ты уже в основной кампании."
        level = eng.current_level()
        comp = eng.module_arena_compose(level) if level else None
        if comp:
            from . import helper
            helper.arena_down(comp)
        ok, _ = eng.switch_track("main")
        return (ok, "Вернулся в основную кампанию." if ok else "Не удалось переключиться.")

    if action == "surprise_start":
        se = SurpriseEngine(db, _content())
        if se.active_id():
            return False, "Ивент уже идёт."
        track = args.get("track")
        return se.start(track if track in ("crypto", "net", "linux") else None)
    if action == "surprise_drop":
        return True, SurpriseEngine(db, _content()).drop()

    if action in ("answer", "flag"):
        text = str(args.get("text", "")).strip()
        if not text:
            return False, "Пустой ввод."
        se = SurpriseEngine(db, _content())
        if se.active_id():
            ok, msg = se.submit(**{action: text})
            if ok:
                return True, msg
        kw = {action: text}
        res = eng.check_boss(**kw) if eng.boss_active() else eng.check(**kw)
        if res.messages:
            return True, "\n".join(res.messages)
        return False, ("Флаг неверный." if action == "flag"
                       else "Ответ не подошёл ни к одному активному заданию.")

    return False, f"Неизвестное действие: {action}"


def _gui_buy(db, eng, pkg: str, allowlist_fn):
    from . import helper
    level = eng.current_level()
    item = next((i for i in (level.shop if level else [])
                 if i.get("package") == pkg or i.get("name") == pkg), None)
    if not item:
        return False, f"В магазине нет «{pkg}»."
    pkg = item["package"]
    price = int(item.get("price", 0))
    p = db.profile()
    if p["coins"] < price:
        return False, f"Не хватает монет: нужно {price}, есть {p['coins']}."
    res = helper.install_package(pkg, allow=allowlist_fn(eng.content))
    if not res.reached:
        return False, "sq-helperd не запущен — монеты не списаны."
    if not res.ok:
        return False, f"Помощник отклонил установку: {res.output[:160]}"
    db.spend_coins(price)
    db.log_event("buy", package=pkg, price=price, dry_run=res.dry_run)
    return True, f"Куплено: {pkg} (−{price} монет)" + (" (dry-run)" if res.dry_run else "")


def _gui_dlc_start(db, eng, module: str):
    m = eng.content.module_by_dlc_id(module)
    if not m:
        return False, f"Нет модуля «{module}»."
    if not eng.dlc_module_unlocked(m):
        if not eng.dlc_available():
            return False, "«Арсенал» заперт — победи босса основного уровня 5."
        return False, f"Модуль {module} ещё закрыт — пройди предыдущий."
    ok, _ = eng.switch_track("dlc", m.id)
    if not ok:
        return False, "Идёт бой — заверши или прерви его."
    eng._ensure_level_quests(m)
    if m.setup and db.kv_get(f"setup_done_{m.id}") != "1":
        eng._run_level_setup(m)
        db.kv_set(f"setup_done_{m.id}", "1")
    comp = eng.module_arena_compose(m)
    note = ""
    if comp:
        from . import helper
        r = helper.arena_up(comp)
        if r.reached and r.ok:
            note = " · полигон поднят" + (" (dry-run)" if r.dry_run else "")
        elif not r.reached:
            note = " · sq-helperd не запущен (полигон подождёт)"
    return True, f"Вошёл в модуль {m.dlc_id} — «{m.name}»" + note


class _db:
    def __enter__(self):
        self.db = DB()
        return self.db
    def __exit__(self, *a):
        self.db.close()


def run(port: int = 8777, open_browser: bool = True) -> int:
    if not (WEBUI / "index.html").is_file():
        print("GUI assets missing:", WEBUI, file=sys.stderr)
        return 1
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    url = f"http://127.0.0.1:{port}/"
    print(f"shellquest GUI on {url}  (Ctrl+C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.port, not a.no_browser))
