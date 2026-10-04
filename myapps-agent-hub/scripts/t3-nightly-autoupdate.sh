#!/usr/bin/env bash
# t3-nightly-autoupdate - single check: update t3 to latest nightly if behind, then restart it.
set -uo pipefail

# Ignore SIGHUP and SIGPIPE so that disconnecting from an SSH/PTY session or T3
# terminating its child terminals upon restart will not kill the script.
trap '' HUP PIPE

export PATH="/home/developer/.npm-global/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/home/developer"

FORCE=false
if [ "${1:-}" = "--force" ] || [ "${1:-}" = "-f" ]; then
  FORCE=true
fi

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
  if [ "$INSTALLED" = "$LATEST" ] && [ "$FORCE" = false ]; then
    echo "[t3-autoupdate] up to date (use --force to reinstall and restart)"
    exit 0
  fi
fi

echo "[t3-autoupdate] updating t3 ${INSTALLED:-unknown} -> $LATEST"
if npm install -g "t3@nightly"; then
  echo "[t3-autoupdate] install OK, triggering detached restart of t3 via supervisorctl..."

  # Choose a writable log file for the detached restart process
  LOGFILE="/var/log/agent-hub/t3-autoupdate.log"
  if ! touch "$LOGFILE" 2>/dev/null; then
    LOGFILE="/tmp/t3-autoupdate.log"
    touch "$LOGFILE" 2>/dev/null || true
  fi

  # Fully detach supervisorctl restart so that terminating the parent terminal/PTY
  # (which happens automatically when T3 server stops) does not interrupt the restart.
  nohup bash -c '
    exec >> "'"$LOGFILE"'" 2>&1
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [t3-autoupdate] Initiating supervisorctl restart t3..."
    supervisorctl restart t3
    sleep 3
    supervisorctl status t3 || true
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [t3-autoupdate] Restart finished: $(t3 --version 2>/dev/null)"
  ' </dev/null >/dev/null 2>&1 &
  disown

  echo "[t3-autoupdate] detached restart initiated in background (log: $LOGFILE)"
  echo "[t3-autoupdate] waiting for t3 to return to RUNNING..."

  # Wait up to 25 seconds for t3 to be RUNNING if the calling terminal is still open
  RESTARTED=false
  for i in $(seq 1 25); do
    sleep 1
    if supervisorctl status t3 2>/dev/null | grep -q "RUNNING"; then
      RESTARTED=true
      break
    fi
  done

  if [ "$RESTARTED" = true ]; then
    echo "[t3-autoupdate] done, now running: $(t3 --version 2>/dev/null)"
  else
    echo "[t3-autoupdate] note: restart in progress or check status with 'supervisorctl status t3'"
  fi
else
  echo "[t3-autoupdate] ERROR: npm install -g t3@nightly failed"
  exit 1
fi
