# Level 9 arena — «citadel»
The finale target: a vulnerable service (remote foothold as an unprivileged
user) plus one clear local-privesc misconfig (e.g. a root cron running a
world-writable script, or a sudo/SUID rule). User flag `CITADEL-USER-7A` in the
user's home, root flag `CITADEL-ROOT-FF` in `/root`. `sq-helperd` builds
`./citadel`, injects freshly-randomised flags, and confirms the session/uid=0
for the arena-side `script` validators. Image scaffold lives in `./citadel`.
