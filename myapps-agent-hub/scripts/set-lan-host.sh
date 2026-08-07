#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: set-lan-host <UMBREL_LAN_IP_OR_HOSTNAME>" >&2
  echo "Example: set-lan-host 192.168.1.100" >&2
  echo "Or:      set-lan-host umbrel.local" >&2
  exit 1
fi

CFG_DIR=/home/developer/.config/agent-hub
CFG="$CFG_DIR/lan-host"

if [ "$(id -u)" -eq 0 ]; then
  install -d -o developer -g developer "$CFG_DIR"
  printf '%s\n' "$1" > "$CFG"
  chown developer:developer "$CFG"
else
  mkdir -p "$CFG_DIR"
  printf '%s\n' "$1" > "$CFG"
fi

echo "Saved LAN host: $1"
echo "Now run 'pair-t3' to generate a correct T3 Code pairing QR code."
