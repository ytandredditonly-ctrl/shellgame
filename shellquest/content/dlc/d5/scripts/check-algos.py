#!/usr/bin/env python3
"""Boss d5 phase 1 — identify the algorithm set.

Offline grader: confirm the shipped challenge.txt really contains the four
distinct hash families the phase asks the player to identify (raw MD5, SHA-1,
SHA-256, and a sha512crypt `$6$` entry). Pass when all four are present; pending
(exit 2) when the artifact is missing — never a false pass/fail.
"""
import os
import re
import sys

HOME = os.environ.get("SQ_HOME") or os.path.expanduser("~")
CHALLENGE = os.path.join(HOME, "sq-arsenal", "d5", "challenge.txt")


def classify(line: str) -> str | None:
    s = line.strip()
    if s.startswith("$6$"):
        return "sha512crypt"
    if re.fullmatch(r"[0-9a-f]{64}", s):
        return "sha256"
    if re.fullmatch(r"[0-9a-f]{40}", s):
        return "sha1"
    if re.fullmatch(r"[0-9a-f]{32}", s):
        return "md5"
    return None


def main() -> int:
    if not os.path.isfile(CHALLENGE):
        return 2
    try:
        lines = open(CHALLENGE).read().splitlines()
    except OSError:
        return 2
    found = {classify(l) for l in lines if l.strip()}
    found.discard(None)
    need = {"md5", "sha1", "sha256", "sha512crypt"}
    return 0 if need.issubset(found) else 2


if __name__ == "__main__":
    sys.exit(main())
