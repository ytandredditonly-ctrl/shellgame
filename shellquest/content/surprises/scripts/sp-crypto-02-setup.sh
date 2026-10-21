#!/bin/bash
set -u
mkdir -p "$HOME/sq-drop"
# ROT13 of "flag: <FLAG>"
printf 'flag: %s\n' "$SQ_SP_FLAG" | tr 'A-Za-z' 'N-ZA-Mn-za-m' > "$HOME/sq-drop/rot.txt"
exit 0
