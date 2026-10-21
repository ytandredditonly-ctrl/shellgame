"""Validators: each is ``check(ctx, spec) -> 'pass' | 'fail' | 'pending'``.

A quest is complete when *all* of its validators return ``pass``. ``pending``
means "not satisfied yet, keep polling" (e.g. a state check); ``fail`` is only
used where a definite negative is meaningful. For MVP both block completion.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

PASS, FAIL, PENDING = "pass", "fail", "pending"


@dataclass
class Context:
    """Everything a validator may read while checking one quest/phase."""

    db: Any
    content_dir: Path
    scripts_dir: Path                      # scripts/ of the owning level
    # Successful command events observed since the quest started.
    commands: list[dict[str, Any]] = field(default_factory=list)
    cwd: str = ""                          # player's current working dir
    visited: list[str] = field(default_factory=list)  # dirs seen by the hook
    answer: str | None = None              # from `sq answer`
    flag: str | None = None                # from `sq flag`
    env: dict[str, str] = field(default_factory=dict)


def _expand(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- file state -------------------------------------------------------
def v_file_exists(ctx: Context, spec: dict) -> str:
    return PASS if Path(_expand(spec["path"])).exists() else PENDING


def v_file_contains(ctx: Context, spec: dict) -> str:
    p = Path(_expand(spec["path"]))
    if not p.is_file():
        return PENDING
    try:
        text = p.read_text(errors="replace")
    except OSError:
        return PENDING
    if "regex" in spec:
        flags = re.MULTILINE
        return PASS if re.search(spec["regex"], text, flags) else PENDING
    needle = spec.get("text", "")
    return PASS if needle in text else PENDING


def v_file_mode(ctx: Context, spec: dict) -> str:
    p = Path(_expand(spec["path"]))
    if not p.exists():
        return PENDING
    mode = oct(p.stat().st_mode & 0o777)[2:].zfill(3)
    return PASS if mode == str(spec["mode"]).zfill(3) else FAIL


def v_file_owner(ctx: Context, spec: dict) -> str:
    import pwd

    p = Path(_expand(spec["path"]))
    if not p.exists():
        return PENDING
    try:
        owner = pwd.getpwuid(p.stat().st_uid).pw_name
    except KeyError:
        owner = str(p.stat().st_uid)
    return PASS if owner == spec["owner"] else FAIL


# --- services / ports (best-effort; graceful when tools absent) -------
def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.returncode, r.stdout + r.stderr
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def v_service_active(ctx: Context, spec: dict) -> str:
    rc, _ = _run(["systemctl", "is-active", "--quiet", spec["unit"]])
    return PASS if rc == 0 else PENDING


def v_service_enabled(ctx: Context, spec: dict) -> str:
    rc, _ = _run(["systemctl", "is-enabled", "--quiet", spec["unit"]])
    return PASS if rc == 0 else PENDING


def _listening_ports() -> set[int]:
    rc, out = _run(["ss", "-tlnH"])
    ports: set[int] = set()
    if rc != 0:
        return ports
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            local = parts[3]
            if ":" in local:
                try:
                    ports.add(int(local.rsplit(":", 1)[1]))
                except ValueError:
                    pass
    return ports


def v_port_listening(ctx: Context, spec: dict) -> str:
    ports = _listening_ports()
    if "port" in spec:
        return PASS if int(spec["port"]) in ports else PENDING
    if "port_not" in spec:
        # "a listener on some port other than N" — common SSH-on-nonstandard case
        others = ports - {int(spec["port_not"])}
        return PASS if others else PENDING
    return PENDING


def v_port_closed(ctx: Context, spec: dict) -> str:
    return PASS if int(spec["port"]) not in _listening_ports() else FAIL


# --- packages / users -------------------------------------------------
def v_package_installed(ctx: Context, spec: dict) -> str:
    rc, _ = _run(["dpkg", "-s", spec["name"]])
    return PASS if rc == 0 else PENDING


def v_user_exists(ctx: Context, spec: dict) -> str:
    import pwd

    try:
        pwd.getpwnam(spec["name"])
        return PASS
    except KeyError:
        return PENDING


def v_group_member(ctx: Context, spec: dict) -> str:
    import grp

    try:
        members = grp.getgrnam(spec["group"]).gr_mem
    except KeyError:
        return PENDING
    return PASS if spec["user"] in members else PENDING


# --- command signal ---------------------------------------------------
def v_command_used(ctx: Context, spec: dict) -> str:
    """One of the named commands ran successfully since the quest began.

    Anti-farm (§6): exit code 0 and the command line must differ byte-for-byte
    from the immediately preceding one (the engine already filters repeats, but
    we guard here too).
    """
    wanted = set(spec.get("any_of", []))
    if "command" in spec:
        wanted.add(spec["command"])
    for ev in ctx.commands:
        if ev.get("exit") != 0:
            continue
        if ev.get("name") in wanted:
            return PASS
    return PENDING


# --- answer / flag ----------------------------------------------------
def _match_answer(answer: str, spec: dict) -> bool:
    ci = spec.get("ci", False)
    cand = answer.strip()
    if ci:
        cand = cand.lower()
    if "answer_sha256" in spec:
        return _sha(cand) == spec["answer_sha256"]
    if "answer" in spec:
        expected = str(spec["answer"])
        return (expected.lower() if ci else expected) == cand
    if "regex" in spec:
        flags = re.IGNORECASE if ci else 0
        return bool(re.fullmatch(spec["regex"], answer.strip(), flags))
    return False


def v_output_matches(ctx: Context, spec: dict) -> str:
    if ctx.answer is None:
        return PENDING
    return PASS if _match_answer(ctx.answer, spec) else FAIL


def v_flag(ctx: Context, spec: dict) -> str:
    if ctx.flag is None:
        return PENDING
    cand = ctx.flag.strip()
    if "sha256" in spec:
        return PASS if _sha(cand) == spec["sha256"] else FAIL
    if "value" in spec:
        return PASS if cand == str(spec["value"]) else FAIL
    return FAIL


# --- arbitrary script -------------------------------------------------
def v_script(ctx: Context, spec: dict) -> str:
    """Run a content script in a sandboxed subprocess; exit 0 => pass.

    Scripts live in the level's ``scripts/`` dir. They are passed the player
    cwd and home via the environment and get a 10s timeout (§6).
    """
    rel = spec["path"] if "path" in spec else spec.get("script", "")
    script = (ctx.scripts_dir / Path(rel).name)
    if not script.is_file():
        return FAIL
    env = dict(os.environ)
    env["SQ_PLAYER_CWD"] = ctx.cwd
    env["SQ_VISITED"] = "\n".join(ctx.visited)
    env["SQ_HOME"] = os.path.expanduser("~")
    if ctx.answer is not None:
        env["SQ_ANSWER"] = ctx.answer
    interp: list[str]
    if script.suffix == ".py":
        interp = ["python3", "-I", str(script)]
    else:
        interp = ["bash", str(script)]
    try:
        r = subprocess.run(
            interp, capture_output=True, text=True, timeout=10, env=env
        )
    except subprocess.TimeoutExpired:
        return PENDING
    except OSError:
        return FAIL
    return PASS if r.returncode == 0 else PENDING


REGISTRY: dict[str, Callable[[Context, dict], str]] = {
    "file_exists": v_file_exists,
    "file_contains": v_file_contains,
    "file_mode": v_file_mode,
    "file_owner": v_file_owner,
    "service_active": v_service_active,
    "service_enabled": v_service_enabled,
    "port_listening": v_port_listening,
    "port_closed": v_port_closed,
    "package_installed": v_package_installed,
    "user_exists": v_user_exists,
    "group_member": v_group_member,
    "command_used": v_command_used,
    "output_matches": v_output_matches,
    "flag": v_flag,
    "script": v_script,
}


def run_validator(ctx: Context, spec: dict) -> str:
    fn = REGISTRY.get(spec.get("type", ""))
    if fn is None:
        return FAIL
    try:
        return fn(ctx, spec)
    except Exception:
        return PENDING
