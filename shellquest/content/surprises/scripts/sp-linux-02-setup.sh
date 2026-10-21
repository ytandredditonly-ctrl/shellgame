#!/bin/bash
set -u
D="$HOME/sq-sandbox"; mkdir -p "$D"
for n in notes data cache report; do echo x > "$D/$n.log"; chmod 644 "$D/$n.log"; done
echo "open to all" > "$D/$SQ_SP_NAME"; chmod 646 "$D/$SQ_SP_NAME"
exit 0
