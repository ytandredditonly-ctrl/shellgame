"""JSON-Schema validation for the content pack (§11).

The engine validates every level/quest/boss/surprise file against these schemas
at load time and refuses to start on an invalid pack. `jsonschema` is used when
present; otherwise a minimal built-in checker covers the required keys so the
game still fails loudly rather than silently mis-loading.
"""
from __future__ import annotations

from typing import Any

try:
    import jsonschema  # type: ignore

    _HAVE_JSONSCHEMA = True
except Exception:  # pragma: no cover
    _HAVE_JSONSCHEMA = False


VALIDATOR_TYPES = [
    "file_exists", "file_contains", "file_mode", "file_owner",
    "service_active", "service_enabled", "port_listening", "port_closed",
    "package_installed", "user_exists", "group_member", "command_used",
    "output_matches", "flag", "script",
]

_validator = {
    "type": "object",
    "required": ["type"],
    "properties": {"type": {"enum": VALIDATOR_TYPES}},
}

LEVEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "integer", "minimum": 0},
        "name": {"type": "string"},
        "target_commands": {"type": "array", "items": {"type": "string"}},
        "xp_required": {"type": "integer", "minimum": 0},
        "command_threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "unlock_packages": {"type": "array", "items": {"type": "string"}},
        "shop": {"type": "array"},
        "story_intro": {"type": "string"},
        "story_outro": {"type": "string"},
        "setup": {"type": ["string", "null"]},
        "teardown": {"type": ["string", "null"]},
    },
}

QUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "type", "title", "validators"],
    "properties": {
        "id": {"type": "string"},
        "type": {"enum": ["tutorial", "practice", "combo", "flag", "repair"]},
        "title": {"type": "string"},
        "brief": {"type": "string"},
        "validators": {"type": "array", "minItems": 1, "items": _validator},
        "requires_quests": {"type": "array", "items": {"type": "string"}},
        "requires_packages": {"type": "array", "items": {"type": "string"}},
        "hints": {"type": "array", "items": {"type": "string"}},
        "xp": {"type": "integer", "minimum": 0},
        "coins": {"type": "integer", "minimum": 0},
    },
}

BOSS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "name", "phases"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "phases": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "validators"],
                "properties": {
                    "id": {"type": "string"},
                    "brief": {"type": "string"},
                    "validators": {"type": "array", "minItems": 1, "items": _validator},
                    "hints": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

SURPRISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "track", "title", "validators"],
    "properties": {
        "id": {"type": "string"},
        "track": {"enum": ["crypto", "net", "linux"]},
        "min_level": {"type": "integer", "minimum": 0},
        "requires_packages": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"},
        "story": {"type": "string"},
        "brief": {"type": "string"},
        "validators": {"type": "array", "minItems": 1, "items": _validator},
        "hints": {"type": "array", "items": {"type": "string"}},
        "setup": {"type": ["string", "null"]},
        "teardown": {"type": ["string", "null"]},
        "codex": {"type": ["string", "null"]},
    },
}


class ContentError(ValueError):
    pass


def _fallback_check(data: dict, schema: dict, where: str) -> None:
    for key in schema.get("required", []):
        if key not in data:
            raise ContentError(f"{where}: missing required key '{key}'")
    # minimal validator-type check
    for v in data.get("validators", []):
        if isinstance(v, dict) and v.get("type") not in VALIDATOR_TYPES:
            raise ContentError(f"{where}: unknown validator type {v.get('type')!r}")


def validate(data: dict, schema: dict, where: str) -> None:
    if _HAVE_JSONSCHEMA:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:  # type: ignore
            raise ContentError(f"{where}: {e.message}") from None
    else:
        _fallback_check(data, schema, where)
