"""SQLite state store: profile, quest state, opened commands, event log.

One row in `profile` holds the whole player profile. Everything else is a
narrow table. The schema is created on demand and migrated by simple
`CREATE TABLE IF NOT EXISTS`, which is enough for the MVP.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    level         INTEGER NOT NULL DEFAULT 0,
    level_xp      INTEGER NOT NULL DEFAULT 0,   -- xp inside the current level
    total_xp      INTEGER NOT NULL DEFAULT 0,   -- lifetime, for stats
    coins         INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL,
    boss_unlocked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quest_state (
    quest_id   TEXT PRIMARY KEY,
    level      INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'available',  -- available|done
    started_at REAL,
    done_at    REAL
);

CREATE TABLE IF NOT EXISTS opened_commands (
    command   TEXT PRIMARY KEY,
    opened_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS flags_submitted (
    flag_id  TEXT PRIMARY KEY,
    at       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hints_bought (
    key     TEXT PRIMARY KEY,   -- "<quest_id>:<n>"
    at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS boss_phase (
    boss_id  TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    status   TEXT NOT NULL DEFAULT 'pending',
    done_at  REAL,
    PRIMARY KEY (boss_id, phase_id)
);

CREATE TABLE IF NOT EXISTS event_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      REAL NOT NULL,
    kind    TEXT NOT NULL,
    payload TEXT NOT NULL   -- JSON
);

-- Append-only audit of host changes for `sq uninstall` rollback (§12).
CREATE TABLE IF NOT EXISTS changes_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      REAL NOT NULL,
    action  TEXT NOT NULL,
    detail  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path=None):
        paths.ensure_dirs()
        self.path = str(path or paths.DB_PATH)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- profile -------------------------------------------------------
    def init_profile(self) -> None:
        cur = self.conn.execute("SELECT 1 FROM profile WHERE id = 1")
        if cur.fetchone() is None:
            self.conn.execute(
                "INSERT INTO profile (id, created_at) VALUES (1, ?)", (time.time(),)
            )
            self.conn.commit()

    def profile(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()

    def set_profile(self, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE profile SET {cols} WHERE id = 1", tuple(fields.values())
        )
        self.conn.commit()

    def add_xp_coins(self, xp: int, coins: int) -> None:
        self.conn.execute(
            "UPDATE profile SET level_xp = level_xp + ?, total_xp = total_xp + ?, "
            "coins = coins + ? WHERE id = 1",
            (xp, xp, coins),
        )
        self.conn.commit()

    def spend_coins(self, coins: int) -> bool:
        p = self.profile()
        if p is None or p["coins"] < coins:
            return False
        self.conn.execute(
            "UPDATE profile SET coins = coins - ? WHERE id = 1", (coins,)
        )
        self.conn.commit()
        return True

    # -- quests --------------------------------------------------------
    def quest_status(self, quest_id: str) -> str | None:
        r = self.conn.execute(
            "SELECT status FROM quest_state WHERE quest_id = ?", (quest_id,)
        ).fetchone()
        return r["status"] if r else None

    def ensure_quest(self, quest_id: str, level: int) -> None:
        if self.quest_status(quest_id) is None:
            self.conn.execute(
                "INSERT INTO quest_state (quest_id, level, status, started_at) "
                "VALUES (?, ?, 'available', ?)",
                (quest_id, level, time.time()),
            )
            self.conn.commit()

    def complete_quest(self, quest_id: str) -> None:
        self.conn.execute(
            "UPDATE quest_state SET status = 'done', done_at = ? WHERE quest_id = ?",
            (time.time(), quest_id),
        )
        self.conn.commit()

    def done_quests(self) -> set[str]:
        return {
            r["quest_id"]
            for r in self.conn.execute(
                "SELECT quest_id FROM quest_state WHERE status = 'done'"
            )
        }

    # -- opened commands ----------------------------------------------
    def open_command(self, command: str) -> bool:
        """Returns True if this is the first time the command is opened."""
        try:
            self.conn.execute(
                "INSERT INTO opened_commands (command, opened_at) VALUES (?, ?)",
                (command, time.time()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def opened_commands(self) -> set[str]:
        return {
            r["command"] for r in self.conn.execute("SELECT command FROM opened_commands")
        }

    # -- flags ---------------------------------------------------------
    def flag_submitted(self, flag_id: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM flags_submitted WHERE flag_id = ?", (flag_id,)
            ).fetchone()
            is not None
        )

    def submit_flag(self, flag_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO flags_submitted (flag_id, at) VALUES (?, ?)",
            (flag_id, time.time()),
        )
        self.conn.commit()

    # -- hints ---------------------------------------------------------
    def hint_bought(self, quest_id: str, n: int) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM hints_bought WHERE key = ?", (f"{quest_id}:{n}",)
            ).fetchone()
            is not None
        )

    def buy_hint(self, quest_id: str, n: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO hints_bought (key, at) VALUES (?, ?)",
            (f"{quest_id}:{n}", time.time()),
        )
        self.conn.commit()

    def hints_opened(self, quest_id: str) -> int:
        r = self.conn.execute(
            "SELECT COUNT(*) c FROM hints_bought WHERE key LIKE ?", (f"{quest_id}:%",)
        ).fetchone()
        return r["c"]

    # -- boss phases ---------------------------------------------------
    def phase_status(self, boss_id: str, phase_id: str) -> str:
        r = self.conn.execute(
            "SELECT status FROM boss_phase WHERE boss_id = ? AND phase_id = ?",
            (boss_id, phase_id),
        ).fetchone()
        return r["status"] if r else "pending"

    def set_phase(self, boss_id: str, phase_id: str, status: str) -> None:
        self.conn.execute(
            "INSERT INTO boss_phase (boss_id, phase_id, status, done_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(boss_id, phase_id) "
            "DO UPDATE SET status = excluded.status, done_at = excluded.done_at",
            (boss_id, phase_id, status, time.time() if status == "done" else None),
        )
        self.conn.commit()

    def reset_boss(self, boss_id: str) -> None:
        self.conn.execute("DELETE FROM boss_phase WHERE boss_id = ?", (boss_id,))
        self.conn.commit()

    # -- events / changes ---------------------------------------------
    def log_event(self, kind: str, **payload: Any) -> None:
        self.conn.execute(
            "INSERT INTO event_log (at, kind, payload) VALUES (?, ?, ?)",
            (time.time(), kind, json.dumps(payload)),
        )
        self.conn.commit()

    def events(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        )

    def log_change(self, action: str, detail: str) -> None:
        self.conn.execute(
            "INSERT INTO changes_log (at, action, detail) VALUES (?, ?, ?)",
            (time.time(), action, detail),
        )
        self.conn.commit()

    # -- kv (misc flags) ----------------------------------------------
    def kv_get(self, k: str, default: str | None = None) -> str | None:
        r = self.conn.execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
        return r["v"] if r else default

    def kv_set(self, k: str, v: str) -> None:
        self.conn.execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = ?",
            (k, v, v),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


@contextmanager
def open_db(path=None) -> Iterator[DB]:
    db = DB(path)
    try:
        yield db
    finally:
        db.close()
