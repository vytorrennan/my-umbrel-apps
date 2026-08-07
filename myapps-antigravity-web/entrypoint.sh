#!/bin/bash
set -e

# Ensure developer ownership of mounted persistent volumes
mkdir -p /home/developer/.config/Antigravity/User/globalStorage /home/developer/.gemini /home/developer/Projects
chown -R developer:developer /home/developer/.config /home/developer/.gemini /home/developer/Projects /home/developer/antigravity-client 2>/dev/null || true

export PORT=${PORT:-8765}
export VERBOSE=${VERBOSE:-1}
export ALLOW_REMOTE=1
export ALLOW_ALL=1
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

STATE_DB_1="/home/developer/.config/Antigravity/User/globalStorage/state.vscdb"
STATE_DB_2="/home/developer/.config/Antigravity IDE/User/globalStorage/state.vscdb"

if [ ! -f "$STATE_DB_1" ] && [ ! -f "$STATE_DB_2" ]; then
  echo "[Antigravity Web] state.vscdb not found. Launching Web Setup Onboarding page on port $PORT..."
  sudo -E -u developer node /home/developer/antigravity-client/onboarding-server.js || true
fi

echo "[Antigravity Web] Starting web UI on port $PORT..."
exec sudo -E -u developer node /home/developer/antigravity-client/dist/src/server/web-poc/server.js /home/developer/Projects
