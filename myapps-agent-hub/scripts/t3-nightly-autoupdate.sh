#!/usr/bin/env bash
# t3-nightly-autoupdate - single check: update t3 to latest nightly if behind, then restart it.
# Runs every 6h via supervisord (see entrypoint.sh [program:t3-nightly-autoupdate]).
set -uo pipefail

export PATH="/home/developer/.npm-global/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/home/developer"

INSTALLED="$(t3 --version 2>/dev/null | awk '{print $2}' | sed 's/^v//')"
LATEST="$(npm view t3 dist-tags.nightly 2>/dev/null | tr -d ' \r\n')"

if [ -z "${LATEST:-}" ]; then
  echo "[t3-autoupdate] WARN: could not resolve latest nightly (npm view failed), skipping"
  exit 0
fi
if [ -z "${INSTALLED:-}" ]; then
  echo "[t3-autoupdate] WARN: could not detect installed version, trying install of $LATEST"
else
  echo "[t3-autoupdate] installed=$INSTALLED latest=$LATEST"
  if [ "$INSTALLED" = "$LATEST" ]; then
    echo "[t3-autoupdate] up to date"
    exit 0
  fi
fi

echo "[t3-autoupdate] updating t3 ${INSTALLED:-unknown} -> $LATEST"
if npm install -g "t3@nightly"; then
  echo "[t3-autoupdate] install OK, restarting t3 via supervisorctl"
  if supervisorctl restart t3; then
    sleep 5
    supervisorctl status t3 || true
    echo "[t3-autoupdate] done, now running: $(t3 --version 2>/dev/null)"
  else
    echo "[t3-autoupdate] ERROR: supervisorctl restart t3 failed"
    exit 1
  fi
else
  echo "[t3-autoupdate] ERROR: npm install -g t3@nightly failed"
  exit 1
fi
