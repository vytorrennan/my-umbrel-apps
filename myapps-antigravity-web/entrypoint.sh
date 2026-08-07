#!/bin/bash
set -e

# Ensure developer ownership of mounted persistent volumes
chown -R developer:developer /home/developer/.config /home/developer/.gemini /home/developer/Projects 2>/dev/null || true

# Switch execution to developer user
exec sudo -E -u developer bash -c '
  export PATH=/home/developer/.local/bin:/home/developer/.fnm/current/bin:$PATH
  export PORT=${PORT:-8765}
  export VERBOSE=${VERBOSE:-1}

  cd /home/developer/antigravity-client
  echo "[Antigravity Web] Starting web UI on port $PORT..."
  exec npx tsx src/server/web-poc/server.ts /home/developer/Projects
'
