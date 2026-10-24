#!/bin/bash
# d1 teardown. Remove only the game-owned module brief; the arena is torn down
# by sq-helperd (sq dlc leave / module victory).
set -u
rm -rf "$HOME/sq-arsenal/d1" 2>/dev/null
exit 0
