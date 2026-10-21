# shellquest

Kali Linux as an RPG. A background hook + the `sq` CLI turn learning the system
into a game with linear progression: a level unlocks a set of tools, quests
teach them, a boss checks the combination, victory raises your level.

The game reads **real system state** — XP is awarded for an actual result (a
file created, a command successfully used, a flag submitted), not for typing the
"right" text. Breaks are never punished: there are no timers or dailies, and
progress persists.

This repository implements the **progression engine** from the design docs
(`shellquest_TZ.md`, `quests-full.md`) — SQLite state, the zsh hook, the
validator set, the `sq` CLI, the prompt indicator — plus **all ten levels of
content** (0–9), each with quests, a 3-phase boss, hints, codex cards and
story. The engine is content-driven: levels are pure YAML + scripts and never
touch the engine code.

### Levels & playability

Every level loads and is structurally complete (all flags ship **hashed**).
How much runs on a bare host depends on what the level touches:

| Lvl | Name | Theme | Runs on host today |
| --- | --- | --- | --- |
| 0 | Пробуждение | filesystem, find, grep | ✅ fully |
| 1 | Хранители | users, permissions, ownership | ✅ fully (sudo quests use your own sudo) |
| 2 | Нутро | processes, services, cron | ◑ process/kill quests ✅; service/journal/cron need `sq-helperd`/root |
| 3 | Конвейер | pipelines, sed/awk, scripts | ✅ fully (deterministic generated logs) |
| 4 | Внешние земли | networking, ssh | ✅ with Docker — `gatekeeper` image (ssh+web+echo) |
| 5 | Крепость | firewall, fail2ban | ◑ with Docker + root — `attacker` image brute-forces you |
| 6 | Разведка | nmap, tcpdump, gobuster | ✅ with Docker — `web`/`db`/`misc` images |
| 7 | Паутина | web / SQLi | ✅ with Docker — vulnerable `juicebox` image |
| 8 | Шифр | hashes, gpg, cracking | ✅ fully (host-local: gpg vaults + crackable hashes) |
| 9 | Последний рубеж | full chain to root | ✅ with Docker — `citadel` (ssh foothold + sudo/find privesc) |

Every arena is a **real, buildable image** under `content/levelN/arena/`
(Dockerfiles + compose on an `internal: true` network). `scripts/verify-arenas.sh`
builds and smoke-tests them. Arena-side `script` validators (e.g. the boss port
map) return **pending**, never a false pass/fail, until graded by `sq-helperd`;
flag-submit phases work standalone.

#### One-time Docker access (needed for levels 4–7, 9)

```bash
sudo usermod -aG docker "$USER"        # then log out/in (or: newgrp docker)
sudo apt-get install -y docker-compose-plugin   # provides `docker compose`
bash shellquest/scripts/verify-arenas.sh         # builds + smoke-tests arenas
```

> Designed to run inside a VM. Level 0 touches only `~/terminal` and the game's
> own state dir, and every change is reversible via `sq uninstall`.

## Install

```bash
./install.sh          # sets up `sq`, wires the zsh hook into ~/.zshrc
exec zsh              # or: source ~/.zshrc
sq init               # create profile, lay out the Level 0 playground
```

No third-party Python packages are required beyond **PyYAML** (already present
on Kali). `install.sh` uses `pip install --user -e .` when available, otherwise
drops a shim at `~/.local/bin/sq`.

Optional background daemon (runs state checks every 30s so services/ports/files
advance without you typing `sq check`):

```bash
cp systemd/sq-daemon.service ~/.config/systemd/user/
systemctl --user enable --now sq-daemon
```

Optional prompt indicator `[L0 ▰▱▱▱▱ 16%]` — set `SQ_PROMPT=1` before the hook
is sourced.

## Playing

```
sq status              # level, XP/threshold, commands opened, coins, boss
sq quests              # quests of the level: available / done / locked
sq quest <id>          # a quest's goal and bought hints
sq check               # force a re-check of active quests
sq answer <text>       # answer for output_matches quests (also surprises)
sq flag <value>        # submit a flag (also surprises)
sq hint <id>           # buy the next hint (10/25/50 coins); `sq hint surprise`
sq codex [<cmd>|sp-id] # opened commands / a command card / a surprise write-up
sq boss start|resume|abort
sq shop | sq buy <pkg> # tool shop (installs via sq-helperd)
sq surprise [crypto|net|linux] | status | drop   # «Детская неожиданность» (§7a)
sq helper              # is sq-helperd up?
sq config [list|get <k>|set <k> <v>]
sq log                 # event history
sq pause | sq resume   # stop/restart tracking for non-game work
sq uninstall           # run level teardowns, print removal steps
```

### Surprise events — «Детская неожиданность» (§7a)

Six events ship (crypto ×3: base64, ROT13, SHA256 integrity; net ×1: hidden
listener; linux ×2: disk hog, world-writable) — all host-playable and tested.
Short side-tasks on three tracks (crypto / net / linux) that don't affect level
progression. The daemon rolls for one during an active session (configurable
chance/cooldown/min-session); `sq surprise` starts one on demand. Each run is
**re-parametrised** (fresh flag/port/filename) so answers can't be memorised —
only a SHA-256 of the expected value is stored. Solving the first time gives
30 XP / 25 coins and unlocks a codex write-up explaining the security lesson;
repeats give coins only. Drop is free (`sq surprise drop`) and fully reverts.
Events touch only `~/sq-drop`, `~/sq-sandbox` and `sq-*` processes, and survive
shutdown. While one is active the prompt shows a `!`.

### GUI companion window — `sq gui`

A read-only companion window (GUI spec). `sq gui` starts a tiny local web
server (stdlib only, no extra installs) on `127.0.0.1:8777` and opens it in your
browser; keep it on a second monitor beside the terminal. It shows the level,
XP ring, open-command chips, a 10-node world map, live quest cards (with
per-validator progress dots), and a sliding manual panel (How-to / Commands /
Codex). It **never mutates state** — buttons copy `sq …` commands to the
clipboard for the terminal. Updates are pushed in real time over Server-Sent
Events: finish a quest in the terminal and its card ticks over instantly. If the
game isn't initialised yet it shows a calm "no connection — run `sq init`"
screen. Flags: `sq gui --port <n>`, `sq gui --no-browser`.

### Helper, installs and arenas

`sq-helperd` is the small root daemon that performs the **only** system-changing
operations the game needs, from a fixed whitelist (`install_package`,
`remove_package`, `arena_up/down`, `apply_breakage`, `revert`) over a Unix
socket — no arbitrary commands, package names are allow-listed against the
content, every change is journaled. `sq buy` installs through it; levels 4–9
bring their Docker arena up on `sq boss start` and down on victory/abort.
Without the helper, `sq buy` keeps your coins and tells you how to start it;
arena phases simply wait. When not run as root it operates in **dry-run** (logs
instead of executing) — handy for development.

### Manual-install watcher (§5)

The daemon tails `dpkg.log`. If a *shop* tool is installed outside the game, the
`install_policy` config decides: `lenient` (default) allows it but it earns
nothing; `strict` removes it again via the helper and points you to `sq shop`.
Base system packages are never touched.

### Level 0 walkthrough (spoiler-light)

`sq init` scatters the Architect's leftovers under `~/terminal`. Explore with
`pwd`/`ls`, enter the folder, read the welcome note and submit its code word,
tidy up (copy, delete `.tmp`, rename), and `grep` out a hidden `PASS=`. Using a
level's target commands successfully **opens** them (XP + a codex card). When
you've opened ≥80% of them and hit the XP threshold, the boss **«Собиратель»**
unlocks: find the scattered `part_*` fragments, reassemble the key, submit it.

## How it works (architecture)

```
zsh hook ──append──▶ events.jsonl ──drain──▶ SQLite ◀── engine ◀── sq CLI / daemon
(preexec/precmd)     (non-blocking)          state      validators      content/*.yaml
```

- **Hook** (`shell/sq-hook.zsh`) reports each command (line, exit, cwd, duration)
  to `sq _hook`, fully detached so the prompt never blocks. Command lines are
  masked for secrets before they are stored (§12 privacy).
- **Engine** (`sq/engine.py`) drains the buffer, opens commands, runs each
  quest's validators, awards XP/coins once, checks the boss-unlock condition
  (XP threshold **and** command-coverage threshold), runs boss phases, and
  levels up.
- **Validators** (`sq/validators/`): `file_exists/contains/mode/owner`,
  `service_active/enabled`, `port_listening/closed`, `package_installed`,
  `user_exists`, `group_member`, `command_used`, `output_matches`, `flag`,
  and `script` (a sandboxed content script, 10s timeout).
- **Content** (`content/levelN/`): `level.yaml`, `quests/*.yaml`, `boss.yaml`,
  `scripts/`, `codex/*.md`. Answers and flags ship **only as SHA-256**.
- **Reward bus** (`sq/events.py`): the `RewardHandler.on_event` interface the
  owner's reward layer subscribes to. MVP ships an empty implementation.

Anti-farm (§6): XP for a quest and for opening a command is granted once;
`command_used` requires exit code 0; byte-identical consecutive commands are
dropped before they ever count.

## Adding content

Drop a new `content/level1/` with the same layout. The loader picks up any
`level*/level.yaml`. To hash an answer or flag for a validator:

```bash
printf '%s' 'nightfall' | sha256sum          # for ci answers, hash the lowercased text
```

Put the hash in `answer_sha256` / `flag.sha256`. See `content/level0` for a
worked example and `quests-full.md` for the full 10-level catalogue to port.

## Scope & safety

Implemented (the whole TZ feature set):
- Engine, SQLite, zsh hook, 15 validators, economy, hints, codex, prompt
  indicator, notifications, **all 10 levels + bosses**, the §8 threshold clamp,
  `pause/resume`, `uninstall`.
- **`sq-helperd`** — root helper with a fixed, allow-listed operation set over a
  Unix socket; dry-run when unprivileged. `sq buy` installs through it.
- **Docker arenas** — real, buildable images for L4 `gatekeeper`, L6
  `web`/`db`/`misc`, L7 `juicebox`, L9 `citadel`, and L5 `attacker`; L8 is
  host-local (gpg provisioning). Brought up/down by the helper around boss
  fights; `scripts/verify-arenas.sh` builds + smoke-tests them.
- **Surprise events** (§7a) — engine, six host-playable events across all three
  tracks, daemon scheduler, rewards, codex write-ups, free drop, rollback.
- **Manual-install watcher** (§5) — `lenient`/`strict` dpkg.log policy.
- **Config** (`~/.config/shellquest/config.yaml`) + `sq config`.
- **JSON-Schema validation** of every content file at load (§11).

The L5 `attacker` and L9 `citadel` images are complete but have only been
built/run where Docker was available to the author — run `scripts/verify-arenas.sh`
in your environment to confirm. The engine runs **unprivileged**; only
`sq-helperd` is root. Attack-style content (levels 6–9) targets only local
training containers on an `internal: true` network — nothing points outward.
