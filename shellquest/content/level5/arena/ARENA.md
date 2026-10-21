# Level 5 arena — «attacker»
Brought up by `sq-helperd` via `arena_up`. One container on the isolated
`sqlab` network that runs a slow SSH brute-force loop against the player's host
(training only, no outbound). Populates `/var/log/auth.log` with `Failed
password` lines. The player wins by: firewall `default deny incoming` + allow 22,
and a fail2ban `sshd` jail that bans the attacker IP. Teardown stops the loop and
reverts any `sq-*` rules. Image: `shellquest/attacker` (hydra + a wordlist).
