#!/bin/bash
# loginbox: real SSH (weak admin password) + an HTTP login form. Internal net.
/usr/sbin/sshd
exec python3 /opt/app.py
