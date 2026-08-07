#!/usr/bin/env bash
set -euo pipefail

DEV_HOME=/home/developer
CFG_DIR="$DEV_HOME/.config/agent-hub"
PW="$(grep '^AGENT_PASSWORD=' "$CFG_DIR/secrets.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"

LAN_HOST="${T3_LAN_HOST:-}"
[ -z "$LAN_HOST" ] && [ -f "$CFG_DIR/lan-host" ] && LAN_HOST="$(cat "$CFG_DIR/lan-host")"
[ -z "$LAN_HOST" ] && LAN_HOST="<umbrel-lan-ip>"

cat <<EOF
Agent Hub
--------
Services (from any device on your network)
  OpenChamber UI : http://$LAN_HOST:3000
  OpenCode web   : http://$LAN_HOST:4096
  T3 Code        : http://$LAN_HOST:3773   (pair with a token)
  Terminal       : http://$LAN_HOST:7682

UI/API password : $PW
Saved in        : $CFG_DIR/secrets.env

Local clients (backend on the server, client on your device)
  OpenCode TUI  : opencode attach http://$LAN_HOST:4096   (user: opencode / password: $PW)
  OpenChamber   : openchamber connect-url --port 3000 --server http://$LAN_HOST:3000 --qr
  T3 Code       : desktop app -> Add environment -> host $LAN_HOST:3773 + token from 'pair-t3'

Management
  set-lan-host <ip>    remember your Umbrel LAN address (do this once)
  pair-t3              mint a fresh T3 Code pairing QR + URL
  agent-logs           tail all service logs
  sudo supervisorctl status
EOF
