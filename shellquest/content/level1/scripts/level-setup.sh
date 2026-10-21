#!/bin/bash
# Level 1 setup: permission puzzles under ~/terminal. Idempotent, host-local.
set -u
T="$HOME/terminal"
mkdir -p "$T/archive" "$T/notes" "$T/bin" "$T/shared" "$T/guard/stash"

# q02: a file whose owner the player must read. Try to make it root-owned to
# teach "system files belong to root"; fall back to player-owned if no
# passwordless sudo. The validator compares against the real owner either way.
printf 'service=idle\nsecret=keeper\n' > "$T/archive/secret.log"
sudo -n chown root:root "$T/archive/secret.log" 2>/dev/null || true

# q03: starts 644, player must tighten to 600.
printf 'private notes\n' > "$T/notes/private.txt"; chmod 644 "$T/notes/private.txt"

# q04: a script without the execute bit.
printf '#!/bin/bash\necho run\n' > "$T/bin/run.sh"; chmod 644 "$T/bin/run.sh"

# q06: a file the player will hand to sq-guest.
printf 'quarterly report\n' > "$T/shared/report.txt"

# boss: exactly one world-writable file; record its path for the validator.
printf 'the door is open\n' > "$T/guard/world_writable.log"
chmod 666 "$T/guard/world_writable.log"
echo "$T/guard/world_writable.log" > "$T/guard/.target"
printf 'PERM-BROKEN-FIXED\n' > "$T/guard/stash/flag.txt"
chmod 600 "$T/guard/stash/flag.txt" 2>/dev/null || true
exit 0
