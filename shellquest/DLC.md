# shellquest DLC «Арсенал» — Architecture & Design

This document explains the **DLC «Арсенал»** («the Arsenal») in detail: the idea
behind it, how it plugs into the base game, how each piece fits together, and how
to extend it. It is the companion to `ARCHITECTURE.md` (the base engine),
`README.md` (install/play), and the source spec `dlc-top10.md`.

> Scope note. The DLC is a **content pack + a focused engine/CLI/loader addition**,
> not a rewrite. The base game's rule — *the engine has no per-level code* — holds:
> all ten modules and the finale are pure YAML + scripts + Docker arenas. The only
> engine changes are a track abstraction, a `sq dlc` CLI surface, and live arena
> graders. Everything a player reads is in Russian; only tool/protocol names stay
> Latin.

---

## 1. The idea

The base game (levels 0–9) teaches Linux fundamentals and basic hardening. The
Arsenal is a **second campaign** layered on top: a focused course in **ten core
information-security tools**, one module per tool, each ending in a boss that
tests the tool in anger, plus a final exam that chains several tools on one
target.

Three commitments carry over from the base game and shape the DLC:

1. **Result, not ritual.** Progress comes from a real outcome — a port found, a
   packet decoded, a hash cracked, a flag recovered — read from the actual
   arena/artifact, never from typing the "right" words.
2. **Tools are earned.** Each module's tool is **bought with coins** in the DLC
   shop (coins carry over from the base campaign), then installed on demand via
   `sq-helperd`. The machine fills with real security tools as you progress.
3. **Local targets only.** Every offensive action points at a **local training
   container** on an `internal: true` Docker network (no outbound) or at an
   offline artifact. Nothing targets real or third-party hosts.

**Story frame.** The Architect left behind «the Arsenal» — ten locked workbenches,
each holding one tool and its own training range. Clearing a bench «claims» that
tool. Beating the finale earns the title «Арсенал освоен» («the Arsenal mastered»).

**The arc** (order is fixed; skills accumulate):

| # | Module | Tool(s) | What it teaches |
| --- | --- | --- | --- |
| d1 | Разведка (Recon) | nmap | hosts, ports, services, versions |
| d2 | Трафик (Traffic) | Wireshark / tshark | reading the wire: DNS/HTTP/TLS |
| d3 | Веб-прокси (Web proxy) | Burp Suite (Community) | intercept & tamper HTTP |
| d4 | Эксплуатация (Exploitation) | Metasploit | exploit → payload → session |
| d5 | Пароли офлайн (Passwords, offline) | John / Hashcat | how passwords are stored & cracked |
| d6 | Онлайн-вход (Online login) | Hydra | brute-forcing live login services |
| d7 | SQL-инъекции (SQLi) | sqlmap | dumping a DB through injection |
| d8 | Wi-Fi | Aircrack-ng | wireless weaknesses (offline) |
| d9 | Веб-recon | Nikto / gobuster / ffuf | finding hidden paths & endpoints |
| d10 | Терминальный захват (Terminal capture) | tcpdump | capturing traffic with no GUI |
| final | Полигон Архитектора (The Architect's Proving Ground) | all | chain recon → web → password → capture |

Order rationale: reconnaissance first (you can't act on what you can't see), then
traffic analysis, web, exploitation, passwords, online attacks, databases, Wi-Fi,
web recon, and finally terminal-only capture — the defender's situation on a bare
server.

---

## 2. How the DLC plugs into the engine

The key realization: **a DLC module *is* a `Level`.** The base engine already
operates on any `Level` (quests + boss + shop + unlock/setup + command/XP
thresholds) through one integer `profile.level` pointer and an `id + 1` advance.
So the DLC reuses all of it with three small, surgical additions.

### 2.1 Modules are Levels with reserved ids

DLC modules live under `content/dlc/dN/` and load as ordinary `Level`s with
**reserved integer ids** so every id-keyed mechanism works unchanged:

```
d1 = 101, d2 = 102, … d10 = 110, final = 111
```

Each `level.yaml` adds three optional fields (`content.py`, `schema.py`):

- `track: dlc` — marks it as DLC (`Level.is_dlc`).
- `dlc_id: d1` — the string handle used by `sq dlc start d1` and shown to players.
- `arena: arena/compose.yaml` — a **module-level** arena (see §2.4).

Because ids are a contiguous high band, `engine._level_up`'s `id + 1` advances
`101 → 102 → … → 111`, and all id-keyed state (`boss_defeated_<id>`,
`setup_done_<id>`, the `xp_clamp` warning), plus string-keyed quest ids
(`d1-q01`), boss ids (`d1-boss`), and the global `opened_commands` set, stay
unique and need no schema change. The only `_level_up` branch: a module with no
successor sets `dlc_complete` instead of the base game's `game_complete`.

### 2.2 Two parallel tracks, no DB migration

The base game is single-track (one `profile.level`). The DLC adds a **second,
parallel track** the player can switch into and out of freely. All of this lives
in the existing `kv` table — **no schema migration**:

| key | meaning |
| --- | --- |
| `track` | the active track: `main` or `dlc` |
| `track_main_level` / `track_main_xp` | the main campaign's parked pointer + XP |
| `track_dlc_level` / `track_dlc_xp` | the DLC's parked pointer + XP |

`engine.switch_track(target, level_id=None)` stashes the live
`profile.level`/`level_xp` into the current track's slots and restores the
target's, so the live `profile` always mirrors the active track. Switching is
**blocked while a boss fight is active** (`boss_active`), so a fight's transient
`boss_unlocked`/phase state can never straddle tracks; `boss_unlocked` re-derives
on the next `sq check`. `_level_up` keeps the active track's `kv` pointer in sync
as it advances.

Consequence: you can play main levels 6–9 and the DLC in parallel, each keeping
its own level pointer and XP. Coins and the `opened_commands` set are **global**
(shared), which is intentional — a tool you opened in the base game counts in the
DLC too, and vice-versa.

### 2.3 Gating: Act-I lock + linear modules

- **DLC lock.** The Arsenal opens only after the **main level-5 boss** is
  defeated (end of Act I): `engine.dlc_available()` ≡ `boss_defeated(5)`.
- **Linear modules.** Within the DLC, `dlc_module_unlocked(m)` requires the
  **previous** module's boss defeated (d1 needs only the Act-I gate). So modules
  open one at a time in order, the same way base levels do.

### 2.4 Module-level arenas (lifecycle)

Base levels raise an arena only for the boss fight. DLC **practice quests** need
their targets live for the whole module (you scan/inject/capture long before the
boss), so the arena is tied to the module, not just its boss:

- `sq dlc start <mod>` raises `module_arena_compose(level)` via `helper.arena_up`
  (idempotent; `start_boss` also raises it).
- `sq dlc leave` and module victory (`_level_up`) lower it via `helper.arena_down`.
- Advancing within the DLC raises the next module's arena on entry.

Offline modules (d5, d8) declare no `arena`; their artifacts are generated by the
module's `setup` script instead.

### 2.5 CLI surface (`sq dlc`)

Added to `cli.py` (`cmd_dlc`); every other command (`quests`, `quest`, `check`,
`answer`, `flag`, `boss`, `shop`, `buy`, `hint`, `codex`, `status`) already
operates on `current_level()` and needed **no change** — in a DLC module they
just act on that module.

```
sq dlc                  # list modules: locked / current / defeated + the Act-I gate
sq dlc start <module>   # switch to the DLC at <module> (if unlocked); raises its arena
sq dlc leave            # lower the arena and return to the main campaign
sq dlc <module>         # shorthand for `sq dlc start <module>`
```

`status`/`quests` print the module label (`d1`) instead of the internal id (101).

---

## 3. Content format (per module)

Identical to a base level (see `ARCHITECTURE.md` §7), under `content/dlc/dN/`:

```
content/dlc/d1/
  level.yaml          # id, dlc_id, track, name, target_commands, xp_required,
                      #   command_threshold, shop (tool + price), arena, setup/teardown, story
  quests/dN-qNN.yaml  # 4–6 quests: type, title, brief, validators, hints, requires_quests
  boss.yaml           # dN-boss: 3 phases (d1–d10) or 4 (finale); flag + script + output_matches
  codex/<tool>.md     # the module's tool reference card (joins the shared `sq codex`)
  scripts/            # idempotent setup/teardown + any script-validator graders
  arena/              # Dockerfiles + compose (internal:true) for container modules
content/dlc/d5|d8/    # offline modules: no arena/, artifacts generated by setup
content/dlc/final/    # the exam: 4-phase boss, hints_enabled:false, proving-ground arena
```

**Quests** are mostly `command_used{tool}` + `output_matches` (a value the player
reads from the live arena/artifact), so they complete standalone. **Answers and
flags ship only as SHA-256** (`printf '%s' '<v>' | sha256sum`; lowercase first for
`ci` answers). The plaintext never lives in a quest/boss YAML — it exists only
inside the arena image (as a banner/route/credential) or a generated artifact, or
as documented training material.

**Setup scripts** are idempotent and game-owned (they write only under
`~/sq-arsenal/dN`), so `sq resetup` is safe after a reboot. Every file is
JSON-Schema-validated at load.

---

## 4. Arenas and offline artifacts

Act-II-style targets, mirroring the base game: real, buildable Docker images on an
`internal: true` network, plus deterministic offline artifacts where hardware
isn't available in a VM.

| Module | Arena / artifact | The real thing inside |
| --- | --- | --- |
| d1 | `recon-net` (alpha/beta/gamma) | three hosts with distinct, deterministic port/service maps |
| d2 | `chatter` + `sample.pcap` | periodic traffic + an offline capture to dissect |
| d3 | `shopfront` | web app trusting a client `role` cookie and a client `qty` |
| d4 | `breach` | a vsftpd-2.3.4-style banner + a `:6200` backdoor shell |
| d5 | offline `hashes`/`shadow`/`wordlist`/`challenge.txt`/`secret.enc` | weak MD5s, a sha512crypt `$6$`, an `unshadow` pair, a mixed-algorithm challenge, an AES file opened by the cracked key |
| d6 | `loginbox` | a real `sshd` + an HTTP login form with a weak credential |
| d7 | `dbshop` | a web app with a **real string-concatenated SQLite injection** + a `vault` table |
| d8 | offline `capture.cap` + `wordlist` | a genuine 802.11 beacon (real ESSID/BSSID); handshake/key are documented training values (a WPA2 handshake can't be synthesised) |
| d9 | `webmaze` | hidden paths, a fuzzable GET param, a forgotten `.bak`, a hidden endpoint |
| d10 | `serverbox` | a service emitting a cleartext token/flag to capture over SSH |
| final | `proving-ground` + `edge` | a leaky `/admin` (credential + crackable hash) and an `edge` banner holding the final flag |

Most container nodes build from one small env-driven Python listener
(`arena/node/serve.py`, driven by `SQ_PORTS`), so ports/services/banners are
deterministic and quest answers are reproducible. `scripts/verify-arenas.sh`
builds and probes every arena (DLC + base).

---

## 5. Live grading (`script` validators)

Boss phases that can't be a plain `flag`/`answer` use a `script` validator. In the
base game these are placeholder stubs that return `pending` (exit 2) until a real
grader exists. **The DLC graders are live** — and they are still *content scripts*,
so no engine change was needed:

- **Container modules** (d1 port-map, d3 Burp tamper, d4 exploit session, d10
  cleartext token) `docker exec` into the running arena on its internal network
  and check the genuine success signal.
- **Offline modules** (d5 algorithm set, d8 ESSID/BSSID) parse the shipped
  artifact directly (d5 classifies the four hash families in `challenge.txt`; d8
  parses the ESSID and BSSID out of the `capture.cap` beacon).

Each grader returns `pass` **only** on the real signal and `pending` otherwise —
**never a false pass/fail** — so a boss `script` phase lights up exactly when the
arena/artifact is in the intended state, and flag/answer phases always work
standalone. Validators run under `python3 -I` with a 10 s timeout, exactly as the
base-game `script` validator specifies.

---

## 6. GUI integration (`snapshot.py`, `webui/`, `gui.py`)

The companion window is DLC-aware and, as of the interactive build, its controls
**act for real**.

- **Snapshot** (`snapshot.py`) exposes `track`, `dlc_available`, the per-module
  `dlc` states (`locked`/`unlocked`/`current`/`defeated`), and the level's
  `dlc_id`/`is_dlc`. `state_version` keys on `track`, so switching tracks pushes a
  fresh snapshot over SSE. The quest/boss panels already render `current_level()`,
  so inside a module they «just work».
- **UI** (`webui/`) adds the «Арсенал» module strip (enter a module, leave the
  track), a DLC-aware top bar, and manual entries.
- **Write path** (`gui.py`, `POST /api/action`) runs a fixed whitelist — `check`,
  `boss_start`/`abort`, `hint`, `buy`, `dlc_start`/`leave`, `surprise_*`,
  `answer`/`flag` — through the *same* `Engine`/`SurpriseEngine` calls the CLI
  makes. No shell, args validated against content. It is bound to `127.0.0.1` and
  rejects cross-site/DNS-rebind calls (localhost `Host` + a required `X-SQ-GUI`
  header a browser only sends same-origin). The snapshot stays the single source
  of truth; after an action the SSE loop re-pushes state.

---

## 7. Economy & balance

Each module's tool is bought in the DLC shop (coins carry across tracks). Prices
scale with tool weight:

| Module | Shop (price in coins) |
| --- | --- |
| d1 | nmap 120 |
| d2 | wireshark 120 (ships `tshark` too) |
| d3 | burpsuite 150 |
| d4 | metasploit-framework 200 |
| d5 | john 120 / hashcat 160 (either suffices) |
| d6 | hydra 120 |
| d7 | sqlmap 140 |
| d8 | aircrack-ng 120 |
| d9 | nikto 80 / gobuster 80 / ffuf 80 (any two cover it) |
| d10 | tcpdump 60 |

XP uses the base economy (tutorial 20 / practice 40 / combo 70; opening a command
10). Every module's `xp_required` is tuned to ≈ 0.67 of its reachable XP (quests +
command opens), so the boss unlocks at roughly two-thirds progress plus the 80 %
command-coverage condition — never unreachable. The **finale** is a pure exam:
0 required XP, no shop, four phases, `hints_enabled: false`.

---

## 8. Security model

- **No outbound.** Every arena network is `internal: true`; attack content points
  only at these local training targets.
- **Flags/answers hashed.** Only SHA-256 lives in shipped YAML; plaintext exists
  only inside arena images or generated artifacts, as in the base game.
- **Privileged ops stay behind the helper.** Tool installs and arena up/down go
  through `sq-helperd`'s fixed, allow-listed operation set — the DLC adds no new
  privileged path. Package names are validated against the content's shop.
- **GUI write path is a fixed whitelist** with no shell, localhost-bound and
  CSRF/rebind-guarded (§6).
- **Graders probe, never mutate** the player's system; they read an arena signal
  or an artifact and map it to pass/pending.

---

## 9. Testing & verification

- **`scripts/regression.py`** (in-process, deterministic) — 76 checks, including
  the DLC block: all 11 modules load with the right id/`dlc_id`/`track`, bosses
  have the right phase counts with XP reachable, flags ship as SHA-256 only, the
  linear unlock chain d1→…→finale holds, the finale has hints disabled, and a
  **solvability guard** confirms all **72** DLC answer/flag hashes are derivable
  from the shipped content (catching any orphaned or typo'd hash a player could
  never satisfy).
- **`scripts/verify-arenas.sh`** — builds and probes every arena (base + DLC):
  26 checks, e.g. d4's `:6200` backdoor flag, d7's UNION-injection → vault flag,
  d6's real `sshd` + form, d9's hidden endpoint.
- **Live grader checks** — each `script` grader passes with its arena/artifact up
  and goes `pending` when it is down.

Run the engine suite:

```bash
HOME=$(mktemp -d) SQ_CONTENT_DIR=$PWD/content python3 scripts/regression.py
```

---

## 10. File map

```
content/dlc/
  d1 … d10/            # one directory per module (Level layout, §3)
  final/               # the proving-ground exam
sq/
  content.py           # Level.{track,dlc_id,arena}; loads content/dlc/*; dlc_modules()/module_by_dlc_id()
  engine.py            # switch_track, dlc_available, dlc_module_unlocked, module_arena_compose; _level_up dlc branch
  cli.py               # cmd_dlc (sq dlc / start / leave)
  schema.py            # optional track/dlc_id/arena on the level schema
  snapshot.py          # track + dlc block in the GUI snapshot; Russian manual (HOWTO/COMMANDS_TABLE)
  gui.py               # POST /api/action write path (whitelisted, guarded)
  webui/               # «Арсенал» strip, action buttons, submit bar
scripts/
  regression.py        # DLC structural + solvability checks
  verify-arenas.sh     # builds + probes DLC arenas
```

---

## 11. Extending the DLC

- **A new module.** Add `content/dlc/dN/` with the Level layout: pick the next id
  in the band, set `dlc_id`/`track: dlc`, give it a `shop` tool + price, 4–6
  quests, a 3-phase boss, a codex card, idempotent setup/teardown, and an
  `arena/` (or offline artifacts). Hash answers/flags with
  `printf '%s' '<v>' | sha256sum`. The loader, `sq dlc`, the GUI, and the linear
  unlock pick it up automatically — no engine edits.
- **A live grader.** Write `scripts/check-*.py` that probes the arena (via
  `docker exec`) or parses the artifact, exits `0` on the genuine signal and `2`
  otherwise, and reference it from a boss phase as
  `{type: script, path: check-*.py}`.
- **Keep it solvable and Russian.** Make sure every new answer/flag is derivable
  from the arena/artifact (the regression solvability guard enforces this), and
  that all player-facing text is Russian.

---

*For the base engine and the full module/boss catalogue rationale, see
`ARCHITECTURE.md` and the source spec `dlc-top10.md`. For install and play, see
`README.md`.*
