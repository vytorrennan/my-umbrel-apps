#!/bin/sh
set -eu

mkdir -p /workspace

# herdr is the thing ttyd serves. Once you're in, launch codex or agy
# (Antigravity CLI) inside a herdr pane and it'll track their status
# in the sidebar like any other supported agent.
ARGS="-W -p 7681"

# Optional HTTP basic auth: set TTYD_CREDENTIAL=user:pass on the service
# in docker-compose.yml. Strongly recommended since this exposes a real
# shell to anyone who can load the page.
if [ -n "${TTYD_CREDENTIAL:-}" ]; then
  ARGS="$ARGS -c ${TTYD_CREDENTIAL}"
fi

cd /root
exec ttyd $ARGS herdr
