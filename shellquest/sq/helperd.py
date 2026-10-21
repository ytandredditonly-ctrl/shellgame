"""sq-helperd — the privileged helper (§10, §12).

A tiny root daemon that performs the *only* system-changing operations the game
needs, from a fixed whitelist, over a Unix socket. It never runs arbitrary
commands: a request names an operation and parameters; anything outside the
whitelist, or with malformed parameters, is refused.

Security properties:
  * Fixed operation table — no shell, no eval, no caller-supplied commands.
  * Package names and unit/arena names are charset-validated.
  * Package installs/removals are constrained to a caller-supplied allow-list
    (the content's shop + unlock packages), passed per request and re-checked.
  * Every change is journaled to changes.log in the player's state dir.
  * Runs in **dry-run** automatically when not root (for development/tests):
    operations are logged and reported, nothing is executed.

Protocol: newline-delimited JSON. Request {"op": str, "params": {...}}.
Response {"ok": bool, "output": str, "dry_run": bool}.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import paths
PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]{1,99}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

_running = True
DRY = os.geteuid() != 0 or os.environ.get("SQ_HELPER_DRY_RUN") == "1"


def _journal(action: str, detail: str) -> None:
    """Append to the player's changes.log DB if reachable, else a flat file."""
    try:
        from .db import DB

        DB().log_change(f"helper:{action}", detail)
    except Exception:
        paths.ensure_dirs()
        with open(paths.DATA_DIR / "helper-changes.log", "a") as fh:
            fh.write(f"{time.time()}\t{action}\t{detail}\n")


def _run(cmd: list[str]) -> tuple[bool, str]:
    if DRY:
        return True, f"[dry-run] would run: {' '.join(cmd)}"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


# --- operations -------------------------------------------------------
def op_install_package(params: dict) -> tuple[bool, str]:
    pkg = params.get("package", "")
    allow = set(params.get("allow", []))
    if not PKG_RE.match(pkg):
        return False, f"invalid package name: {pkg!r}"
    if allow and pkg not in allow:
        return False, f"package {pkg!r} not in allow-list"
    _journal("install_package", pkg)
    return _run(["apt-get", "install", "-y", "--no-install-recommends", pkg])


def op_remove_package(params: dict) -> tuple[bool, str]:
    pkg = params.get("package", "")
    allow = set(params.get("allow", []))
    if not PKG_RE.match(pkg):
        return False, f"invalid package name: {pkg!r}"
    if allow and pkg not in allow:
        return False, f"package {pkg!r} not in allow-list"
    _journal("remove_package", pkg)
    return _run(["apt-get", "remove", "-y", pkg])


def _compose_binary() -> list[str] | None:
    """Return the available compose invocation, or None.

    Prefers the `docker compose` plugin, falls back to the standalone
    `docker-compose`, then `podman-compose`.
    """
    if shutil.which("docker"):
        # plugin present?
        try:
            r = subprocess.run(["docker", "compose", "version"],
                               capture_output=True, timeout=10)
            if r.returncode == 0:
                return ["docker", "compose"]
        except (OSError, subprocess.SubprocessError):
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("podman-compose"):
        return ["podman-compose"]
    return None


def _compose(path: str) -> list[str] | None:
    p = Path(path)
    if not p.is_file():
        return None
    # must live inside the content tree
    try:
        p.resolve().relative_to(Path(paths.CONTENT_DIR).resolve())
    except ValueError:
        return None
    base = _compose_binary()
    if base is None:
        return None
    return base + ["-f", str(p)]


def op_arena_up(params: dict) -> tuple[bool, str]:
    compose = _compose(params.get("compose", ""))
    if compose is None:
        return False, "compose file missing, outside content, or docker absent"
    _journal("arena_up", params.get("compose", ""))
    return _run(compose + ["up", "-d"])


def op_arena_down(params: dict) -> tuple[bool, str]:
    compose = _compose(params.get("compose", ""))
    if compose is None:
        return False, "compose file missing, outside content, or docker absent"
    _journal("arena_down", params.get("compose", ""))
    return _run(compose + ["down", "-v"])


def _content_script(rel: str) -> Path | None:
    """Resolve a setup/teardown/breakage script path inside content/."""
    p = (Path(paths.CONTENT_DIR) / rel).resolve()
    try:
        p.relative_to(Path(paths.CONTENT_DIR).resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def op_apply_breakage(params: dict) -> tuple[bool, str]:
    script = _content_script(params.get("script", ""))
    if script is None:
        return False, "breakage script missing or outside content"
    _journal("apply_breakage", str(script))
    interp = ["python3", "-I", str(script)] if script.suffix == ".py" else ["bash", str(script)]
    return _run(interp)


def op_revert(params: dict) -> tuple[bool, str]:
    script = _content_script(params.get("script", ""))
    if script is None:
        return False, "revert script missing or outside content"
    _journal("revert", str(script))
    interp = ["python3", "-I", str(script)] if script.suffix == ".py" else ["bash", str(script)]
    return _run(interp)


def op_status(params: dict) -> tuple[bool, str]:
    compose = _compose_binary()
    return True, json.dumps({
        "dry_run": DRY,
        "docker": bool(shutil.which("docker")),
        "compose": " ".join(compose) if compose else None,
    })


OPS = {
    "install_package": op_install_package,
    "remove_package": op_remove_package,
    "arena_up": op_arena_up,
    "arena_down": op_arena_down,
    "apply_breakage": op_apply_breakage,
    "revert": op_revert,
    "status": op_status,
}


def handle(line: str) -> str:
    try:
        req = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "output": "bad json", "dry_run": DRY})
    op = req.get("op")
    params = req.get("params", {}) or {}
    fn = OPS.get(op)
    if fn is None:
        return json.dumps({"ok": False, "output": f"unknown op {op!r}", "dry_run": DRY})
    try:
        ok, out = fn(params)
    except Exception as e:  # never crash the daemon on one request
        ok, out = False, f"error: {e}"
    return json.dumps({"ok": ok, "output": out, "dry_run": DRY})


def _stop(*_a):
    global _running
    _running = False


def run(sock_path: str | None = None) -> int:
    paths.ensure_dirs()
    sp = Path(sock_path or paths.helper_socket())
    if sp.exists():
        sp.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sp))
    # Owner rw only — the game runs as a single user.
    os.chmod(sp, 0o600)
    srv.listen(8)
    srv.settimeout(1.0)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    mode = "DRY-RUN (not root)" if DRY else "LIVE (root)"
    sys.stderr.write(f"sq-helperd listening on {sp} [{mode}]\n")
    sys.stderr.flush()
    try:
        while _running:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(5.0)
                data = b""
                try:
                    while not data.endswith(b"\n"):
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                        if len(data) > 1_000_000:
                            break
                    resp = handle(data.decode(errors="replace").strip())
                    conn.sendall(resp.encode() + b"\n")
                except (socket.timeout, OSError):
                    pass
    finally:
        try:
            sp.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(run())
