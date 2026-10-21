#!/bin/bash
# shellquest installer (MVP). Sets up the `sq` command, the zsh hook, and
# (optionally) the user daemon. Does NOT require root for the game engine.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
HOOK_LINE="source \"$HERE/shell/sq-hook.zsh\""

echo "shellquest installer"
echo "  checkout: $HERE"

# 1. Make `sq` runnable. Prefer a pip install; fall back to a shim wrapper.
if command -v pip3 >/dev/null 2>&1; then
  echo "  installing package (pip install --user -e .)"
  pip3 install --user -e "$HERE" >/dev/null 2>&1 && INSTALLED=1 || INSTALLED=0
else
  INSTALLED=0
fi

if [[ "$INSTALLED" != "1" ]]; then
  mkdir -p "$HOME/.local/bin"
  cat > "$HOME/.local/bin/sq" <<EOF
#!/bin/bash
exec python3 -m sq "\$@"
EOF
  chmod +x "$HOME/.local/bin/sq"
  # Ensure the package is importable: add checkout to PYTHONPATH via the shim.
  sed -i "1a export PYTHONPATH=\"$HERE:\${PYTHONPATH:-}\"" "$HOME/.local/bin/sq"
  echo "  created shim: ~/.local/bin/sq (ensure ~/.local/bin is on PATH)"
fi

# 2. Wire up the zsh hook (idempotent).
if ! grep -qsF "$HERE/shell/sq-hook.zsh" "$ZSHRC" 2>/dev/null; then
  {
    echo ""
    echo "# shellquest"
    echo "$HOOK_LINE"
  } >> "$ZSHRC"
  echo "  hook added to $ZSHRC"
else
  echo "  hook already present in $ZSHRC"
fi

# 3. Write a default config if none exists.
python3 -c "import sys; sys.path.insert(0,'$HERE'); from sq import config; config.write_default()" 2>/dev/null \
  && echo "  config: ~/.config/shellquest/config.yaml"

echo ""
echo "Done. Open a new zsh shell (or: source $ZSHRC), then:"
echo "    sq init"
echo ""
echo "Optional background daemon (quest/boss checks, surprise rolls, dpkg"
echo "watcher — every ~30s):"
echo "    mkdir -p ~/.config/systemd/user"
echo "    cp $HERE/systemd/sq-daemon.service ~/.config/systemd/user/"
echo "    systemctl --user enable --now sq-daemon"
echo ""
echo "Privileged helper sq-helperd (needed for apt installs via 'sq buy' and"
echo "Docker arenas on levels 4-9). It performs ONLY a fixed operation set:"
echo "    sudo cp $HERE/systemd/sq-helperd.service /etc/systemd/system/"
echo "    sudo systemctl enable --now sq-helperd"
echo "  Check it from the game with:  sq helper"
echo ""
echo "Config: sq config list | sq config set surprises false | ..."
