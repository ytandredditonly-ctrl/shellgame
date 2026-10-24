#!/bin/bash
# d5 teardown. Remove only the game-owned module dir; arenas are torn
# down by sq-helperd (sq dlc leave / module victory).
set -u
rm -rf "$HOME/sq-arsenal/d5" 2>/dev/null
exit 0
