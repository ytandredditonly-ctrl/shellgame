# ufw — простой firewall

- `sudo ufw allow 22/tcp` / `deny 23/tcp`
- `sudo ufw default deny incoming`
- `sudo ufw default allow outgoing`
- `sudo ufw enable`; `ufw status verbose`

Под капотом — nftables. `man ufw`.
