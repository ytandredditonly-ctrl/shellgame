#!/bin/bash
set -u
D="$HOME/sq-sandbox"
mkdir -p "$D"
# a handful of small files + one clearly-largest file with the random name
for i in 1 2 3 4 5; do head -c $((RANDOM%2000+100)) /dev/zero > "$D/pad_$i.bin"; done
head -c 500000 /dev/zero > "$D/$SQ_SP_NAME"
exit 0
