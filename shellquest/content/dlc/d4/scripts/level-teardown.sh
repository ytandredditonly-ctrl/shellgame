#!/bin/bash
# d4 teardown. Remove only the game-owned module dir; arenas are torn
# down by sq-helperd (sq dlc leave / module victory).
set -u
rm -rf "$HOME/sq-arsenal/d4" 2>/dev/null
exit 0
