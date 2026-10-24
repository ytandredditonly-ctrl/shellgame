# shellquest — Architecture & Design

This document explains **what shellquest is**, the ideas behind it, and **how
every part fits together**. It is the companion to `README.md` (how to install
and play), `shellquest_TZ.md` (the product spec), and `quests-full.md` (the
content catalogue). If you are extending the engine or writing content, start
here.

---

## 1. The idea

shellquest turns learning Kali Linux into a linear RPG. You start on a
near-empty machine as the new operator of an abandoned system ("the Terminal")
left behind by a predecessor known as **the Architect**. You level up by
actually *using* the system.

Three design commitments shape everything:

1. **Result, not ritual.** Progress is earned by a real change in system state —
   a file created, a service started, a port opened, a flag recovered — or by a
   command that genuinely ran and exited `0`. Typing the "right" text into the
   game proves nothing; the game reads the real system.
2. **Tools are earned.** The base image ships with coreutils and shell builtins
   only. Everything else (nmap, sqlmap, hashcat, …) is **bought in-game** with
   coins and installed on demand. The game is designed for a clean machine that
   fills with tools as you progress.
3. **Breaks are never punished.** No timers, no dailies, no decay. Progress is
   durable; you resume exactly where you left off.

The arc runs across **10 levels in two acts**: Act I (0–5) is Linux fundamentals
and hardening your own machine; Act II (6–9) is security practice against local
training targets the game brings up. Each level unlocks a toolset, teaches it
through quests, and ends with a **boss** that tests the combination. Beating the
boss is the only way to advance.

---

## 2. System at a glance

```
  ┌────────────┐   command events    ┌──────────────┐
  │  zsh hook  │ ──(non-blocking)──▶  │ events.jsonl │   (append-only buffer)
  │ preexec/   │                      └──────┬───────┘
  │ precmd     │                             │ drain (on `sq`, or daemon tick)
  └────────────┘                             ▼
                                      ┌──────────────┐     ┌──────────────┐
   player ── `sq ...` CLI ──────────▶ │   engine     │ ───▶│   SQLite     │
                                      │ (progression)│◀─── │  state.db    │
   GUI (sq gui) ──SSE/HTTP──────────▶ │  validators  │     └──────────────┘
                                      └──────┬───────┘
                                             │ privileged ops (install, arena,
                                             ▼  breakage) over a Unix socket
                                      ┌──────────────┐     ┌──────────────┐
                                      │  sq-helperd  │ ───▶│ apt / docker │
                                      │ (root, fixed │     │  compose     │
                                      │  op set)     │     └──────────────┘
                                      └──────────────┘
```

Two privilege domains:

- **Unprivileged** — the hook, the `sq` CLI, the engine, the daemon, the GUI.
  They run as the player and own all game logic. They never change the system.
- **Privileged** — `sq-helperd`, a tiny root daemon that performs only a
  **fixed whitelist** of system-changing operations. It is the sole component
  that touches apt, Docker, or system files.

The **source of truth** is SQLite plus the content pack. The GUI and the daemon
are both just drivers over the same engine; neither owns state.

---

## 3. Module map (`sq/`)

| Module | Responsibility |
| --- | --- |
| `paths.py` | XDG locations for state/config/runtime; the Unix-socket path helper (AF_UNIX length-safe). |
| `db.py` | SQLite layer: profile, quest state, opened commands, flags, hints, boss phases, event log, changes log, a `kv` table. One file; schema created on demand. |
| `config.py` | `~/.config/shellquest/config.yaml` merged over defaults (surprise odds, poll interval, install policy, helper socket, …). |
| `schema.py` | JSON-Schema validation of every content file at load (levels, quests, bosses, surprises). Refuses to start on an invalid pack. |
| `content.py` | Loads the YAML content pack into dataclasses (`Level`, `Quest`, `Phase`, `Boss`). Holds the economy defaults and hint prices. |
| `events.py` | The command pipeline: `append_event` (hook → buffer), `drain_buffer` (buffer → event log, with name extraction + anti-farm), `recent_commands`, and the reward event bus. |
| `validators/__init__.py` | The 15 validators; each is `check(ctx, spec) -> pass|fail|pending`. |
| `engine.py` | Progression core: open commands, run validators, award XP/coins, unlock/run the boss, level up, the threshold clamp, hints. Pure logic over DB + content. |
| `surprises.py` | «Детская неожиданность» side-events: eligibility, parametrisation, lifecycle, rewards, rollback, random scheduler. |
| `watcher.py` | Tails `dpkg.log`; enforces the manual-install policy (lenient/strict). |
| `helper.py` | Client for `sq-helperd` (thin Unix-socket RPC). |
| `helperd.py` | The root daemon: fixed operation table, allow-lists, change journaling, dry-run when unprivileged. |
| `daemon.py` | `sq-daemon`: periodic tick — quest/boss checks, the dpkg watcher, the surprise roll. |
| `snapshot.py` | Builds the read-only state snapshot the GUI consumes; the manual's command table + how-to. |
| `gui.py` | `sq gui`: a stdlib HTTP + Server-Sent-Events server that serves the SPA and pushes state. |
| `webui/` | The single-page app (`index.html`, `app.css`, `app.js`). |
| `cli.py` | The `sq` command-line interface (argparse). All player commands + the internal `_hook`/`_prompt`. |

---

## 4. How a command becomes progress

This is the heart of the game. The flow is deliberately **non-blocking** for the
shell and **anti-farm** by construction.

1. **Capture** (`shell/sq-hook.zsh`). zsh's `preexec` records the command line
   and a start time; `precmd` grabs the exit code, cwd, and duration. It calls
   `sq _hook` **fully detached** (backgrounded, fds to `/dev/null`) so the
   prompt never waits on the game.
2. **Buffer** (`events.append_event`). `sq _hook` does not touch the main DB on
   the hot path. It appends one JSON line — `{cmd, exit, cwd, dur}` — to
   `events.jsonl`, **masks secrets** (passwords/tokens in args are redacted
   before storage), and records the cwd + session timing.
3. **Drain** (`events.drain_buffer`). On any `sq` invocation (or a daemon tick),
   buffered lines are moved into the SQLite `event_log`. For each line it:
   - **extracts the command name(s)** via `_command_names`, which unwraps
     `sudo`/`doas` (skipping their options and `env FOO=bar` prefixes) and takes
     basenames — so `sudo /usr/sbin/useradd -m x` credits **both** `sudo` and
     `useradd`, and `ss` is seen even when invoked as `/usr/bin/ss`;
   - **drops byte-identical consecutive repeats** (you cannot spam one command).
4. **Open** (`engine._process_command_opens`). For each drained event that
   **exited 0**, every name that is a target command of the current level and
   is not already open is **opened once**: XP + coins, a codex card unlocks, and
   a `command_opened` event fires (the GUI animates it live).
5. **Validate** (`validators.v_command_used` and friends). Quests whose
   validators reference commands scan the logged events for a successful use.

Key properties: it reacts to **real successful execution**, the hook is
**non-blocking**, secrets are **masked before storage**, and both
XP-for-opening and quest credit are granted **once**. It only sees commands in a
zsh shell that sourced the hook — which is why container/arena work submits
flags and answers instead of relying on `command_used`.

---

## 5. Progression model

State lives in one `profile` row plus narrow tables. Per level:

- **XP** (`level_xp`) accumulates within the level and resets on level-up;
  lifetime XP is kept for stats.
- **Coins** are the currency for the shop and hints; they carry across levels
  and never decay.

**Boss unlock** requires *both* conditions (`engine.boss_conditions_met`):

1. `level_xp >= effective_xp_required(level)`, and
2. opened target commands ≥ `command_threshold` (default 80%).

`effective_xp_required` applies the **clamp** from the spec: if a level's
authored `xp_required` exceeds the XP the level can actually yield
(`sum(quest xp) + 10 × target_commands`), it is lowered to that maximum and the
event is logged once. This keeps authored content playable even when the quest
set is smaller than the threshold assumed.

**Boss fight** (`engine.start_boss` / `check_boss` / `abort_boss`): phases are
sequential; only the first not-done phase is evaluated each check. When all
phases pass → `_level_up`: mark the boss defeated (so it can't re-unlock),
advance the level, reset `level_xp`, tear the arena down, run the next level's
setup, and install its `unlock_packages` via the helper. If there is no next
level, the game is marked complete.

**Hints** cost coins (default 10/25/50), are bought one tier at a time, and stay
open once purchased. The final boss can disable hints or double their price.

**Economy defaults** (overridable per item in content): tutorial 20 XP / 5,
practice 40 / 10, combo 70 / 25, flag 50 / 30, repair 60 / 40; opening a command
10 / 5; solving a surprise 30 / 25 (first time) then 10 coins on repeats.

### Tracks (main + DLC «Арсенал»)

The DLC is a **second, parallel track** that opens once the main level-5 boss is
defeated. It needs no per-module engine code: DLC modules are ordinary `Level`s
loaded from `content/dlc/dN/` with reserved integer ids (`d1=101 … d10=110`,
`final=111`), `track: dlc`, a string `dlc_id`, and an optional module-level
`arena` (up for the whole module, since DLC quests need their targets live before
the boss). So `engine._level_up`'s `id + 1` advance and all id-keyed state
(`boss_defeated_<id>`, quests, phases) work unchanged; the only `_level_up` branch
is `dlc_complete` vs `game_complete` at the end of a track.

**No schema migration** — per-track state lives in the existing `kv` table:
`track` (active, `main`|`dlc`) plus `track_{main,dlc}_level` / `track_{main,dlc}_xp`.
`engine.switch_track` stashes the live `profile.level`/`level_xp` into the current
track's slots and restores the target's; the live `profile` always mirrors the
active track. It is blocked while a boss fight is active (so transient
`boss_unlocked`/phase state can't straddle tracks; `boss_unlocked` re-derives on
the next `sq check`). `sq dlc` lists/enters modules (`dlc_available` gates on the
Act-I boss, `dlc_module_unlocked` enforces linear order); the arena is raised on
`sq dlc start` and lowered on `sq dlc leave`/victory via the same helper RPC.

**All eleven modules are authored** (`content/dlc/d1…d10` + `final`), all on the
d1 template and pure content — no engine/CLI/schema changes beyond the foundation.
Each module ships `level.yaml` (tool shop item + price, `xp_required` ≤ its
reachable XP, optional module `arena`), 4–6 quests, a boss (`d1…d10`: three phases
= `output_matches` / `script` / `flag`; `final`: four phases, `hints_enabled:
false`), a codex card, and idempotent setup/teardown under `~/sq-arsenal/dN`.
Mandatory quests use only `command_used` + `output_matches`/`file_exists` so they
complete standalone; arena-side grading (`script`) appears only in boss phases.
Unlike the main game's placeholder stubs, the **DLC `script` graders are live**:
each probes its running arena over Docker (`docker exec` into the arena net),
and the offline modules parse the shipped artifact directly (d5 classifies the
hash families in `challenge.txt`; d8 parses ESSID/BSSID from the `capture.cap`
beacon). A grader returns `pass` only on the genuine success signal and `pending`
(exit 2) otherwise — never a false pass/fail — so flag/answer phases always work
standalone and `script` phases light up once the arena/artifact is present
(`scripts/verify-arenas.sh` exercises every one). Container arenas (`chatter`, `shopfront`, `breach`, `loginbox` with a real
`sshd`, `dbshop` with a real SQLite SQLi, `webmaze`, `serverbox`, `proving-ground`)
are buildable `internal:true` images; d5/d8 are host-local/offline, their artifacts
(`hashes`/`shadow`/`wordlist`, `capture.cap`) generated deterministically by setup.
Every answer is reproducible from an arena banner/route, a generated file, or
documented training material; flags/answers are stored only as SHA-256.

---

## 6. Validators

A quest or boss phase is complete when **all** its validators return `pass`.
`pending` means "not satisfied yet, keep polling"; `fail` is a definite
negative. Each is `check(ctx, spec) -> "pass"|"fail"|"pending"`.

| Group | Validators |
| --- | --- |
| Files | `file_exists`, `file_contains` (text/regex), `file_mode`, `file_owner` |
| Services/ports | `service_active`, `service_enabled`, `port_listening`, `port_closed` |
| System | `package_installed`, `user_exists`, `group_member` |
| Signals | `command_used` (from the event log) |
| Answers | `output_matches` (`sq answer`, plain/regex/SHA-256, case-insensitive option) |
| Flags | `flag` (`sq flag`, compared by value or SHA-256) |
| Custom | `script` (a content script in a sandboxed subprocess, 10 s timeout) |

The `Context` carries the DB, the recent command events, the player cwd, visited
dirs, and the pending answer/flag. `script` validators receive `SQ_PLAYER_CWD`,
`SQ_VISITED`, `SQ_HOME`, and `SQ_ANSWER` in their environment, run with
`python3 -I` (isolated) or `bash`, and map exit 0 → pass, non-zero → pending,
timeout → pending. Arena-side scripts deliberately exit `2` (→ pending) until a
real arena/helper grades them, so they never give a false pass or fail.

---

## 7. Content format

All content is data under `content/`, decoupled from the engine. The loader
picks up any `level*/level.yaml`. One level is one directory:

```
content/level4/
  level.yaml          # id, name, target_commands, xp_required, shop, story, setup/teardown
  quests/*.yaml       # id, type, title, brief, validators, requires_quests, hints, xp/coins
  boss.yaml           # id, name, arena, phases[] (each a brief + validators + hints)
  scripts/*.sh|*.py   # setup/teardown + script validators (idempotent)
  codex/*.md          # per-command reference cards
  arena/              # Dockerfiles + compose for Act II targets
content/surprises/
  *.yaml  scripts/  codex/
```

Answers and flags ship **only as SHA-256** — the plaintext never lives in the
pack. Setup scripts are idempotent and touch only game-owned entities
(`~/terminal`, `~/sq-drop`, `~/sq-sandbox`, `sq-*` units/processes), so they can
be re-run safely (`sq resetup`). Every file is JSON-Schema-validated at load.

---

## 8. Surprise events (`surprises.py`)

Short side-tasks on three tracks (crypto / net / linux) that don't affect level
progression. The daemon rolls for one during an active session (configurable
chance, cooldown, minimum session length, and track rotation); `sq surprise`
starts one on demand. Each run is **re-parametrised** — a fresh flag, port,
filename, etc. — so answers can't be memorised; only a SHA-256 of the expected
value is stored in the active state. Solving the first time gives 30 XP / 25
coins and unlocks a codex write-up explaining the security lesson; repeats give
coins only. `sq surprise drop` is free and fully reverts. While one is active the
prompt and GUI show a `!`.

---

## 9. The helper and the security model (`helperd.py`)

The engine never changes the system. Everything privileged goes through
`sq-helperd`, which enforces a hard boundary:

- **Fixed operation table** — `install_package`, `remove_package`,
  `arena_up`, `arena_down`, `apply_breakage`, `revert`, `status`. No shell, no
  `eval`, no caller-supplied commands.
- **Validated parameters** — package names are charset-checked **and** must be
  in a caller-supplied allow-list (the content's shop + unlock packages).
  Compose/breakage paths must resolve **inside the content tree**.
- **Journaling** — every change is written to the changes log for rollback.
- **Dry-run when unprivileged** — run as non-root it logs intended operations
  instead of executing (used in development and tests). `SQ_HELPER_FORCE_LIVE`
  lets a docker-group user drive arenas live without root.
- **Shared socket** — the root daemon and the unprivileged client agree on a
  socket path (`SQ_HELPER_SOCKET`, default `/run/shellquest/helperd.sock`); when
  root, the socket is world-rw because the *op set*, not socket perms, is the
  security boundary.

`sq buy` spends coins only after the helper confirms the install. On level-up the
new level's `unlock_packages` are installed the same way. If the helper isn't
running, `sq buy` keeps your coins and tells you how to start it.

---

## 10. Arenas (`content/level*/arena/`)

Act II targets are real Docker images on an `internal: true` network (no
outbound). They are brought up by the helper on `sq boss start` and down on
victory/abort.

- **L4 `gatekeeper`** — sshd (key-only) + a welcome web service + an echo
  service; mounts the player's public key for the boss SSH phase.
- **L6 `web`/`db`/`misc`** — a recon network: nginx-fingerprinted web with a
  hidden path and a non-standard port, a version-banner service, a credential
  leaker.
- **L7 `juicebox`** — a deliberately vulnerable web app (SQLi auth bypass,
  hidden parameter, admin flag).
- **L9 `citadel`** — a weak-password SSH foothold plus a clear local-privesc
  misconfig (`sudo find` → root).
- **L5 `attacker`** — an SSH brute-force loop against the player's host.
- **L8** is host-local (gpg vaults + crackable hashes), no container.

`scripts/verify-arenas.sh` builds and smoke-tests every arena. Attack-style
content never points outward — only at these local training targets.

---

## 11. The dpkg watcher (`watcher.py`)

Because tools are meant to be earned, the daemon tails `dpkg.log`. If a *shop*
package is installed outside the game, `install_policy` decides: `lenient`
(default) allows it but it earns nothing (noted once); `strict` removes it again
via the helper and points the player to `sq shop`. Base system packages are
never in scope.

---

## 12. The GUI (`gui.py`, `webui/`)

`sq gui` starts a stdlib HTTP server on `127.0.0.1` and opens a dark
single-page companion window. It is **read-only**: it renders the snapshot from
`snapshot.py` and pushes updates over Server-Sent Events whenever a cheap
`state_version` changes; buttons copy `sq …` commands to the clipboard rather
than running them. It shows the top status bar, an XP ring with the two
boss-unlock conditions, open-command chips, a 10-node world map, live quest
cards with per-validator dots, and a sliding manual (How-to / Commands / Codex).
If the game isn't initialised it shows a calm "no connection" screen.

Routes: `/` + assets, `/api/state`, `/api/stream` (SSE), `/api/codex?tool=`,
`/api/manual`.

---

## 13. State, storage, and locations

| What | Where |
| --- | --- |
| SQLite state | `~/.local/share/shellquest/state.db` |
| Command buffer | `~/.local/share/shellquest/events.jsonl` |
| Config | `~/.config/shellquest/config.yaml` |
| Helper socket | `/run/shellquest/helperd.sock` (or per-user runtime dir) |
| Content pack | ships with the package (`content/`), overridable via `SQ_CONTENT_DIR` |

The DB holds the profile, quest/phase status, opened commands, submitted flags,
bought hints, the event log, a changes log (for `sq uninstall` rollback), and a
`kv` table for everything else (boss-active flag, session timing, surprise
state, dpkg offset, clamp warnings, …).

---

## 14. Lifecycle

- **Install** (`install.sh`) — put `sq` on PATH, wire the zsh hook into
  `.zshrc`, write default config. Optional: the `sq-daemon` user unit and the
  `sq-helperd` system unit.
- **`sq init`** — create the profile, baseline the package set, lay out level 0.
- **Play** — use the shell; run `sq status/quests/check/answer/flag/shop/buy/
  hint/codex/boss/surprise/gui`. `sq pause`/`resume` stop tracking for non-game
  work. `sq resetup` restores a level's environment (e.g. after a reboot the
  userspace markers are gone).
- **`sq uninstall`** — run level teardowns and print removal steps; the changes
  log allows returning the system to the `sq init` baseline.

---

## 15. Design decisions worth knowing

- **Non-blocking hook over a buffer file**, not a synchronous socket call — the
  shell must never wait on the game.
- **Full state push on change** (SSE) rather than a granular event protocol —
  simpler and robust; the frontend diffs for animation.
- **Anti-farm is structural**, not heuristic: once-per-command and once-per-quest
  XP, `exit 0` required, consecutive-duplicate suppression.
- **Secrets masked before they are ever written** (privacy, spec §12).
- **The op whitelist is the trust boundary**, which is why socket permissions can
  be relaxed for a single-user training VM.
- **Content is pure data**; the engine has no per-level code. New levels and
  surprises drop in as YAML + scripts.
- **Marker processes use `setsid`** so they survive the spawning process exiting
  (they still don't survive a reboot — hence `sq resetup`).

---

## 16. Extending

- **A new level**: add `content/levelN/` with the standard layout. Hash answers
  with `printf '%s' '<answer>' | sha256sum` (lowercase first for `ci` answers).
  Keep setup scripts idempotent and game-owned.
- **A new surprise**: add `content/surprises/sp-*.yaml` + scripts + a codex card;
  use `params` generators (`random_flag`, `random_word`, `random_port`,
  `random_name`, `random_int`) and reference them in validators as
  `{{ params.x | sha256 }}`.
- **A new validator**: add a function to `validators/REGISTRY` and the type to
  `schema.VALIDATOR_TYPES`.
- **Testing**: `scripts/regression.py` runs the full in-process suite (content
  validation, engine, crypto, surprises, watcher). `scripts/verify-arenas.sh`
  builds and smoke-tests the Docker arenas.

---

*For the product rationale and the full quest/boss catalogue, see
`shellquest_TZ.md` and `quests-full.md`. For install and play, see `README.md`.*
