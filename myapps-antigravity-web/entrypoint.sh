#!/bin/bash
set -e

# Ensure developer ownership of mounted persistent volumes
mkdir -p /home/developer/.config /home/developer/.gemini /home/developer/Projects
chown -R developer:developer /home/developer/.config /home/developer/.gemini /home/developer/Projects /home/developer/antigravity-client 2>/dev/null || true

export PORT=${PORT:-8765}
export VERBOSE=${VERBOSE:-1}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

echo "[Antigravity Web] Starting web UI on port $PORT..."
exec sudo -E -u developer node /home/developer/antigravity-client/dist/src/server/web-poc/server.js /home/developer/Projects
