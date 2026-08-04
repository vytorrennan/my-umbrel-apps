#!/bin/sh
set -eu

mkdir -p /workspace

# herdr is the thing ttyd serves. Once you're in, launch codex or agy
# (Antigravity CLI) inside a herdr pane and it'll track their status
# in the sidebar like any other supported agent.
#
# TERM/COLORTERM/SHELL are set as image-wide ENV vars (see Dockerfile) so
# ttyd inherits them and passes them down to herdr and every pane it
# spawns -- without these, panes fall back to /bin/sh (no tab completion)
# and lose color rendering.
ARGS="-W -p 7681"

# Optional HTTP basic auth: set TTYD_CREDENTIAL=user:pass on the service
# in docker-compose.yml. Strongly recommended since this exposes a real
# shell to anyone who can load the page.
if [ -n "${TTYD_CREDENTIAL:-}" ]; then
  ARGS="$ARGS -c ${TTYD_CREDENTIAL}"
fi

cd /root
exec ttyd $ARGS herdr
