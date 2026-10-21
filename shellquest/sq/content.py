"""Load the YAML content pack into light dataclasses.

Content layout (§11 of the TZ):

    content/
      level0/
        level.yaml
        quests/*.yaml
        boss.yaml
        scripts/*.sh|*.py
        codex/*.md

Answers and flags are stored only as SHA-256 in shipped content; the loader
never needs the plaintext.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import paths
from . import schema

# Default economy placeholders (§8). Content may override per item.
XP_DEFAULTS = {"tutorial": 20, "practice": 40, "combo": 70, "flag": 50, "repair": 60}
COIN_DEFAULTS = {"tutorial": 5, "practice": 10, "combo": 25, "flag": 30, "repair": 40}
HINT_PRICES = [10, 25, 50]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class Quest:
    id: str
    level: int
    type: str
    title: str
    brief: str
    validators: list[dict[str, Any]]
    requires_quests: list[str] = field(default_factory=list)
    requires_packages: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    xp: int = 0
    coins: int = 0
    setup: str | None = None
    teardown: str | None = None
    codex: str | None = None

    @property
    def hint_prices(self) -> list[int]:
        return HINT_PRICES[: len(self.hints)]


@dataclass
class Phase:
    id: str
    brief: str
    validators: list[dict[str, Any]]
    hints: list[str] = field(default_factory=list)


@dataclass
class Boss:
    id: str
    name: str
    level: int
    phases: list[Phase]
    story_brief: str = ""
    arena: str | None = None
    time_limit: Any = None
    hints_enabled: bool = True
    hint_multiplier: float = 1.0


@dataclass
class Level:
    id: int
    name: str
    dir: Path
    target_commands: list[str]
    xp_required: int
    command_threshold: float = 0.8
    unlock_packages: list[str] = field(default_factory=list)
    shop: list[dict[str, Any]] = field(default_factory=list)
    story_intro: str = ""
    story_outro: str = ""
    setup: str | None = None
    teardown: str | None = None
    quests: dict[str, Quest] = field(default_factory=dict)
    boss: Boss | None = None


def _load_yaml(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def load_level(level_dir: Path) -> Level:
    meta = _load_yaml(level_dir / "level.yaml")
    schema.validate(meta, schema.LEVEL_SCHEMA, str(level_dir / "level.yaml"))
    level = Level(
        id=int(meta["id"]),
        name=meta.get("name", f"Level {meta['id']}"),
        dir=level_dir,
        target_commands=list(meta.get("target_commands", [])),
        xp_required=int(meta.get("xp_required", 0)),
        command_threshold=float(meta.get("command_threshold", 0.8)),
        unlock_packages=list(meta.get("unlock_packages", [])),
        shop=list(meta.get("shop", [])),
        story_intro=meta.get("story_intro", ""),
        story_outro=meta.get("story_outro", ""),
        setup=meta.get("setup"),
        teardown=meta.get("teardown"),
    )

    qdir = level_dir / "quests"
    if qdir.is_dir():
        for qf in sorted(qdir.glob("*.yaml")):
            d = _load_yaml(qf)
            schema.validate(d, schema.QUEST_SCHEMA, str(qf))
            qtype = d.get("type", "practice")
            q = Quest(
                id=d["id"],
                level=level.id,
                type=qtype,
                title=d.get("title", d["id"]),
                brief=d.get("brief", ""),
                validators=list(d.get("validators", [])),
                requires_quests=list(d.get("requires_quests", [])),
                requires_packages=list(d.get("requires_packages", [])),
                hints=list(d.get("hints", [])),
                xp=int(d.get("xp", XP_DEFAULTS.get(qtype, 40))),
                coins=int(d.get("coins", COIN_DEFAULTS.get(qtype, 10))),
                setup=d.get("setup"),
                teardown=d.get("teardown"),
                codex=d.get("codex"),
            )
            level.quests[q.id] = q

    bf = level_dir / "boss.yaml"
    if bf.is_file():
        b = _load_yaml(bf)
        schema.validate(b, schema.BOSS_SCHEMA, str(bf))
        phases = [
            Phase(
                id=p["id"],
                brief=p.get("brief", ""),
                validators=list(p.get("validators", [])),
                hints=list(p.get("hints", [])),
            )
            for p in b.get("phases", [])
        ]
        level.boss = Boss(
            id=b["id"],
            name=b.get("name", b["id"]),
            level=level.id,
            phases=phases,
            story_brief=b.get("story_brief", ""),
            arena=b.get("arena"),
            time_limit=b.get("time_limit"),
            hints_enabled=bool(b.get("hints_enabled", True)),
            hint_multiplier=float(b.get("hint_multiplier", 1.0)),
        )
    return level


class Content:
    """All loaded levels, keyed by level id."""

    def __init__(self, content_dir: Path | None = None):
        self.dir = Path(content_dir or paths.CONTENT_DIR)
        self.levels: dict[int, Level] = {}
        self._load()

    def _load(self) -> None:
        if not self.dir.is_dir():
            return
        for ld in sorted(self.dir.glob("level*")):
            if (ld / "level.yaml").is_file():
                lvl = load_level(ld)
                self.levels[lvl.id] = lvl

    def level(self, level_id: int) -> Level | None:
        return self.levels.get(level_id)

    @property
    def max_level(self) -> int:
        return max(self.levels) if self.levels else 0
