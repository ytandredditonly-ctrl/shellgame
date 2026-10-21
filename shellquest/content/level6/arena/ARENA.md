# Level 6 arena — reconnaissance network
`compose.yaml` defines 3 hosts on the internal `sqlab` net with varied, known
open ports so the recon quests and the «Картограф» boss can be graded against a
fixed port map (checked by `sq-helperd`, which knows the ground truth):
- `web`  — 80 (nginx) + one non-standard port (8443)
- `db`   — an outdated service with a recognisable version banner
- `misc` — a plaintext service that periodically leaks a password on :80 for the
  tcpdump quest, and a hidden `/backup` path for the gobuster quest.
