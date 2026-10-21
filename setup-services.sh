#!/bin/bash
# Installs: (A) sq-helperd as a system service (for `sq buy` + Docker arenas),
#           (B) the Level 2 sq-demo.service + cron entry (for quests q04-q06).
# Run with sudo. Creates only sq-* units/files; nothing else is touched.
set -eu
REPO=/home/m/Projects/LinuxGame/shellquest
PLAYER=m
SOCK=/run/shellquest/helperd.sock

echo "== shellquest service setup =="

# --- A. sq-helperd system service -----------------------------------
echo "[A] installing sq-helperd.service ..."
cat > /etc/systemd/system/sq-helperd.service <<UNIT
[Unit]
Description=shellquest privileged helper (fixed operation set)
After=network.target docker.service

[Service]
Type=simple
Environment=PYTHONPATH=$REPO
Environment=SQ_CONTENT_DIR=$REPO/content
Environment=SQ_HELPER_SOCKET=$SOCK
ExecStartPre=/bin/mkdir -p /run/shellquest
ExecStart=/usr/bin/python3 -m sq.helperd
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# point the player's client at the same socket
sudo -u "$PLAYER" env HOME=/home/$PLAYER XDG_CONFIG_HOME=/home/$PLAYER/.config \
  python3 -c "import sys;sys.path.insert(0,'$REPO');from sq import config,paths;config.write_default()" 2>/dev/null || true
# write helper_socket into the player's config
CFG=/home/$PLAYER/.config/shellquest/config.yaml
mkdir -p "$(dirname "$CFG")"
if ! grep -q '^helper_socket:' "$CFG" 2>/dev/null; then
  echo "helper_socket: $SOCK" >> "$CFG"
else
  sed -i "s|^helper_socket:.*|helper_socket: $SOCK|" "$CFG"
fi
chown -R "$PLAYER:$PLAYER" "$(dirname "$CFG")"

# --- B. Level 2 demo service + cron ---------------------------------
echo "[B] installing sq-demo.service (stopped) + sq-revive cron ..."
cat > /etc/systemd/system/sq-demo.service <<UNIT
[Unit]
Description=shellquest demo service (level 2)

[Service]
ExecStart=/bin/sh -c 'echo "START-CODE: lantern"; exec sleep infinity'
UNIT

mkdir -p /opt/sq
cat > /opt/sq/revive.sh <<'RV'
#!/bin/sh
# harmless level-2 "reviver" — the boss quest is to disable this cron entry.
exit 0
RV
chmod +x /opt/sq/revive.sh
echo '* * * * * root /opt/sq/revive.sh >/dev/null 2>&1' > /etc/cron.d/sq-revive
chmod 644 /etc/cron.d/sq-revive

# --- apply -----------------------------------------------------------
systemctl daemon-reload
systemctl enable --now sq-helperd
echo
echo "Done."
echo "  sq-helperd: $(systemctl is-active sq-helperd)"
echo "  sq-demo.service installed but NOT started (that's quest l2-q04)."
echo
echo "Next, as your normal user:"
echo "  sq helper                 # should say available"
echo "  sudo systemctl start sq-demo   # completes l2-q04"
echo "  journalctl -u sq-demo | grep START-CODE   # answer for l2-q05"
echo "  grep -r revive /etc/cron*  # find revive.sh -> answer for l2-q06"
