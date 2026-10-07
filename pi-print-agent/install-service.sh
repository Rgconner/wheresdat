#!/bin/bash
# Run on the Pi itself, from inside this directory, after it's been
# copied to /home/rgcon/wheresdat-print (matches wheresdat-print.service's
# WorkingDirectory/ExecStart paths).
set -euo pipefail

TARGET=/home/rgcon/wheresdat-print

if [ "$(pwd)" != "$TARGET" ]; then
    echo "Run this from $TARGET (copy this whole pi-print-agent/ directory there first)."
    exit 1
fi

# /dev/usb/lp0 is root:lp, 0660 — rgcon needs to be in the lp group to
# write it without running the whole service as root. Confirmed live:
# this is a one-time account change, group membership persists across
# reboots/service restarts (unlike a session-scoped `newgrp`).
if ! groups rgcon | grep -qw lp; then
    echo "Adding rgcon to the lp group (needed to write /dev/usb/lp0 without root)..."
    sudo usermod -aG lp rgcon
    echo "NOTE: group membership only takes effect in a NEW login session --"
    echo "log out/in (or reboot) before the service can actually print."
fi

# Stable /dev/label-40x30 and /dev/label-20x10 names per printer model —
# see 99-wheresdat-labels.rules. Re-trigger so already-plugged printers
# get their links now, not on next replug.
sudo cp 99-wheresdat-labels.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usbmisc

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

sudo cp wheresdat-print.service /etc/systemd/system/wheresdat-print.service
sudo systemctl daemon-reload
sudo systemctl enable wheresdat-print.service
sudo systemctl restart wheresdat-print.service

echo "Installed. Check status with: sudo systemctl status wheresdat-print"
echo "Follow logs with:            journalctl -u wheresdat-print -f"
