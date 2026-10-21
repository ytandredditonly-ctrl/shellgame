#!/bin/bash
# Level 8 setup: provision crackable crypto artefacts (host-local, no Docker).
set -u
bash "$(dirname "$0")/provision.sh"
exit 0
