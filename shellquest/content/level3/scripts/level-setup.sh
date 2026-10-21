#!/bin/bash
set -u
python3 -I "$(dirname "$0")/gen-logs.py"
exit 0
