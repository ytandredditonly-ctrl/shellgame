#!/bin/sh
# Emit a recognisable, outdated service banner so `nmap -sV` identifies it.
exec socat -T2 TCP-LISTEN:5432,reuseaddr,fork SYSTEM:'echo "PostgreSQL 9.3.0 (outdated)"; cat'
