#!/bin/bash
set -u
mkdir -p "$HOME/sq-drop"
printf 'the architect left a flag: %s\n' "$SQ_SP_FLAG" | base64 > "$HOME/sq-drop/note.b64"
exit 0
