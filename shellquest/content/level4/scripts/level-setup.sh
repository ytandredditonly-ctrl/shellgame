#!/bin/bash
# Level 4 arena setup is delegated to sq-helperd (Docker net internal:true).
# This placeholder exports the arena host for quests when the helper is present.
set -u
export SQ_ARENA_HOST="${SQ_ARENA_HOST:-gatekeeper.lab}"
echo "[level4] arena is managed by sq-helperd; see arena/compose.yaml" >&2
exit 0
