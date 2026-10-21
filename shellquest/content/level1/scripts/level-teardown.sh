#!/bin/bash
set -u
rm -rf "$HOME/terminal/guard" "$HOME/terminal/shared" "$HOME/terminal/bin"
# Remove the user the game created, if present (needs sudo; best-effort).
sudo -n userdel -r sq-guest 2>/dev/null || true
exit 0
