#!/bin/bash
set -u
D="$HOME/sq-drop/files"; mkdir -p "$D"
# five legit files
for n in alpha bravo charlie delta echo; do echo "content of $n v1" > "$D/$n.txt"; done
# the tampered one uses the random param name; create it legit first
echo "content original" > "$D/$SQ_SP_NAME"
( cd "$D" && sha256sum ./*.txt ./"$SQ_SP_NAME" > SHA256SUMS 2>/dev/null )
# now tamper it so the checksum no longer matches
echo "TAMPERED by the architect" > "$D/$SQ_SP_NAME"
exit 0
