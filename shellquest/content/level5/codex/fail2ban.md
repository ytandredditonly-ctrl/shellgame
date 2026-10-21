# fail2ban — автобан по журналам

- джейлы описываются в /etc/fail2ban/jail.local
- `fail2ban-client status` — список джейлов
- `fail2ban-client status sshd` — забаненные IP
- банит после N неудач за время

`man jail.conf`.
