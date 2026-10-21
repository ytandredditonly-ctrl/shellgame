"""Client for sq-helperd. Thin, dependency-free Unix-socket RPC."""
from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from . import config, paths


class HelperResult:
    def __init__(self, ok: bool, output: str, dry_run: bool = False, reached: bool = True):
        self.ok = ok
        self.output = output
        self.dry_run = dry_run
        self.reached = reached  # False when the daemon could not be contacted

    def __bool__(self) -> bool:
        return self.ok


def _socket_path() -> str:
    return config.get("helper_socket") or paths.helper_socket()


def available() -> bool:
    return Path(_socket_path()).exists()


def request(op: str, timeout: float = 620.0, **params: Any) -> HelperResult:
    sp = _socket_path()
    if not Path(sp).exists():
        return HelperResult(False, "sq-helperd not running", reached=False)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(sp)
        s.sendall((json.dumps({"op": op, "params": params}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        s.close()
        data = json.loads(buf.decode().strip() or "{}")
        return HelperResult(
            bool(data.get("ok")), data.get("output", ""), bool(data.get("dry_run"))
        )
    except (OSError, json.JSONDecodeError) as e:
        return HelperResult(False, f"helper error: {e}", reached=False)


# Convenience wrappers ------------------------------------------------
def install_package(pkg: str, allow: list[str] | None = None) -> HelperResult:
    return request("install_package", package=pkg, allow=allow or [])


def remove_package(pkg: str, allow: list[str] | None = None) -> HelperResult:
    return request("remove_package", package=pkg, allow=allow or [])


def arena_up(compose: str) -> HelperResult:
    return request("arena_up", compose=compose)


def arena_down(compose: str) -> HelperResult:
    return request("arena_down", compose=compose)


def apply_breakage(script: str) -> HelperResult:
    return request("apply_breakage", script=script)


def revert(script: str) -> HelperResult:
    return request("revert", script=script)


def status() -> HelperResult:
    return request("status", timeout=5.0)
