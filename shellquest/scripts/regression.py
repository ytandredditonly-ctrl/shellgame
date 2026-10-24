#!/usr/bin/env python3
"""Comprehensive shellquest regression. Drives the engine in-process so it is
deterministic and doesn't depend on a shell. Run:

    HOME=<sandbox> SQ_CONTENT_DIR=<repo>/content python3 scripts/regression.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SQ_CONTENT_DIR", os.path.join(ROOT, "content"))
for v in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    os.environ.pop(v, None)

# isolated HOME per run
HOME = tempfile.mkdtemp(prefix="sqreg-")
os.environ["HOME"] = HOME

from sq.db import DB            # noqa: E402
from sq.content import Content  # noqa: E402
from sq.engine import Engine    # noqa: E402
from sq.surprises import SurpriseEngine  # noqa: E402
from sq import events, watcher, config   # noqa: E402

P = F = 0
def check(name, cond):
    global P, F
    if cond:
        P += 1; print(f"  PASS {name}")
    else:
        F += 1; print(f"  FAIL {name}")

def fresh():
    import shutil
    for d in (".local", ".config", "terminal", "sq-drop", "sq-sandbox"):
        shutil.rmtree(os.path.join(HOME, d), ignore_errors=True)
    db = DB(); db.init_profile()
    return db

def feed(db, *cmds, cwd=None):
    cwd = cwd or HOME
    for c in cmds:
        events.append_event(c, 0, cwd)
    events.drain_buffer(db)

print("== content loads + validates ==")
c = Content()
check("10 main levels", set(range(10)).issubset(c.levels))
se_pool = SurpriseEngine(fresh(), c).pool
check("6 surprises", len(se_pool) == 6)
for lid, lv in c.levels.items():
    check(f"L{lid} boss has phases", bool(lv.boss and lv.boss.phases))

print("\n== engine: command open + quest + anti-farm ==")
db = fresh(); eng = Engine(db, c)
eng._run_level_setup(c.level(0))
feed(db, "pwd", "ls")
r = eng.check()
check("q01 completes on pwd+ls", "l0-q01" in r.newly_done_quests)
check("pwd opened once", db.opened_commands() >= {"pwd", "ls"})
xp1 = db.profile()["level_xp"]
feed(db, "pwd", "pwd")  # repeats
eng.check()
check("anti-farm: repeat pwd gives no xp", db.profile()["level_xp"] == xp1)

print("\n== engine: unreachable-threshold clamp (L4) ==")
db = fresh(); eng = Engine(db, c)
db.set_profile(level=4)
lv4 = c.level(4)
check("L4 clamp < requested", eng.effective_xp_required(lv4) <= eng.available_xp(lv4) < lv4.xp_required)

print("\n== level 8 crypto provisioning (host-local) ==")
db = fresh(); eng = Engine(db, c); db.set_profile(level=8)
subprocess.run(["bash", os.path.join(ROOT, "content/level8/scripts/provision.sh")],
               env={**os.environ, "HOME": HOME})
C = os.path.join(HOME, "terminal/crypto")
def gpg_d(f, pw):
    return subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback",
                           "--passphrase", pw, "-d", os.path.join(C, f)],
                          capture_output=True, text=True).stdout
check("vault.gpg -> CIPHER-OPEN-55", "CIPHER-OPEN-55" in gpg_d("vault.gpg", "architect"))
check("final.gpg -> VAULT-CRACKED-404", "VAULT-CRACKED-404" in gpg_d("final.gpg", "matrix"))

print("\n== surprises: all 6 solve ==")
db = fresh(); se = SurpriseEngine(db, c); db.set_profile(level=2)
import codecs, glob
def start_specific(sid):
    for _ in range(120):
        db.kv_set("surprise_active", ""); db.kv_set("surprise_cooldown_until", "0")
        db.kv_set("surprise_track_history", "[]")
        se.start(se.pool[sid].track)
        a = se._active()
        if a and a["id"] == sid:
            return a
    return None
# crypto-01 base64
a = start_specific("sp-crypto-01"); import base64
flag = base64.b64decode(open(HOME+"/sq-drop/note.b64").read()).decode().split()[-1]
feed(db, "base64 -d note.b64", cwd=HOME); ok, _ = se.submit(flag=flag)
check("sp-crypto-01", ok)
# crypto-02 rot13
a = start_specific("sp-crypto-02")
flag = codecs.decode(open(HOME+"/sq-drop/rot.txt").read(), "rot13").split("flag:")[1].strip()
feed(db, "tr", cwd=HOME); ok, _ = se.submit(flag=flag); check("sp-crypto-02", ok)
# crypto-03 integrity
a = start_specific("sp-crypto-03")
out = subprocess.run(["sha256sum","-c","SHA256SUMS"], cwd=HOME+"/sq-drop/files",
                     capture_output=True, text=True).stdout
bad = [os.path.basename(l.rsplit(":",1)[0]) for l in out.splitlines() if "FAILED" in l]
feed(db, "sha256sum -c SHA256SUMS", cwd=HOME); ok,_ = se.submit(answer=bad[0]); check("sp-crypto-03", ok)
# net-01 listener
a = start_specific("sp-net-01")
import time; time.sleep(1)
port = open(HOME+"/.sq-listener-port").read().strip()
feed(db, "ss -tlnp", cwd=HOME); ok,_ = se.submit(answer=port); check("sp-net-01", ok)
# linux-01 big file
a = start_specific("sp-linux-01")
big = os.path.basename(max(glob.glob(HOME+"/sq-sandbox/*"), key=os.path.getsize))
feed(db, "du -a sq-sandbox", cwd=HOME); ok,_ = se.submit(answer=big); check("sp-linux-01", ok)
# linux-02 world-writable
a = start_specific("sp-linux-02")
out = subprocess.run(["find", HOME+"/sq-sandbox","-perm","-0002","-type","f"],
                     capture_output=True, text=True).stdout
ww = os.path.basename(out.strip().splitlines()[0])
feed(db, "find -perm", cwd=HOME); ok,_ = se.submit(answer=ww); check("sp-linux-02", ok)

print("\n== dpkg watcher (lenient/strict) ==")
db = fresh();
log = os.path.join(HOME, "dpkg.log"); os.environ["SQ_DPKG_LOG"] = log
import importlib; importlib.reload(watcher)
open(log,"w").write("2026-01-01 00:00:00 install nmap:amd64 <none> 7.9\n"
                    "2026-01-01 00:00:01 install vim:amd64 <none> 9.0\n")
msgs = watcher.scan(db, c)
check("lenient flags shop pkg (nmap)", any("nmap" in m for m in msgs))
check("lenient ignores base pkg (vim)", not any("vim" in m for m in msgs))

print("\n== DLC «Арсенал» track ==")
dlc_mods = c.dlc_modules()
if dlc_mods:
    d1 = c.module_by_dlc_id("d1")
    check("d1 module loads (id 101, track dlc)", bool(d1) and d1.id == 101 and d1.is_dlc)
    check("d1 boss has 3 phases", bool(d1.boss) and len(d1.boss.phases) == 3)
    check("d1 arena declared", d1.arena == "arena/compose.yaml")
    db = fresh(); eng = Engine(db, c); db.set_profile(level=6, level_xp=33)
    check("DLC locked before L5 boss defeated", not eng.dlc_available())
    db.kv_set("boss_defeated_5", "1")
    check("DLC available after L5 boss defeated", eng.dlc_available())
    check("d1 unlocked, d2+ not (linear)",
          eng.dlc_module_unlocked(d1)
          and all(not eng.dlc_module_unlocked(m) for m in dlc_mods if m.dlc_id != "d1"))
    ok, _ = eng.switch_track("dlc", d1.id)
    check("switch to DLC d1", ok and eng.level_id == 101 and eng.active_track() == "dlc")
    eng._ensure_level_quests(d1)
    check("d1 quests load (5)", len(d1.quests) == 5)
    # nmap scan (command_used) + the live-host answer completes d1-q01
    feed(db, "nmap -sn reconnet")
    r = eng.check(answer="3")
    check("d1-q01 completes on nmap + answer 3", "d1-q01" in r.newly_done_quests)
    dlc_xp = db.profile()["level_xp"]
    ok, _ = eng.switch_track("main")
    check("switch back to main restores L6 + xp",
          ok and eng.level_id == 6 and db.profile()["level_xp"] == 33
          and eng.active_track() == "main")
    ok, _ = eng.switch_track("dlc")
    check("resume DLC restores d1 + its xp",
          ok and eng.level_id == 101 and db.profile()["level_xp"] == dlc_xp)
else:
    check("DLC present (skipped — no dlc content)", True)

print(f"\n==== RESULT: {P} passed, {F} failed ====")
sys.exit(1 if F else 0)
