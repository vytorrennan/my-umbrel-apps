#!/usr/bin/env bash
# Update to the latest nightly and verify the server after a detached restart.
set -uo pipefail
trap '' HUP PIPE

DEV_HOME=/home/developer
export PATH="$DEV_HOME/.npm-global/bin:$DEV_HOME/.fnm/aliases/default/bin:$DEV_HOME/.fnm/current/bin:$DEV_HOME/.fnm:$DEV_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export NPM_CONFIG_PREFIX="$DEV_HOME/.npm-global"
export NPM_CONFIG_USERCONFIG="$DEV_HOME/.npmrc"

# Query the executable of the process actually listening on T3's port. Reading
# /proc/PID/exe also works if npm has replaced the binary on disk since startup.
running_version() {
  python3 - <<'PYVERSION'
import os
import subprocess
from pathlib import Path

inodes = set()
for table in ('/proc/net/tcp', '/proc/net/tcp6'):
    for line in Path(table).read_text().splitlines()[1:]:
        fields = line.split()
        if fields[3] == '0A' and int(fields[1].split(':')[1], 16) == 3773:
            inodes.add('socket:[' + fields[9] + ']')
for process in Path('/proc').iterdir():
    if not process.name.isdigit():
        continue
    try:
        if process.stat().st_uid != os.getuid():
            continue
        for fd in (process / 'fd').iterdir():
            if os.readlink(fd) in inodes:
                output = subprocess.check_output(
                    [str(process / 'exe'), '--version'],
                    text=True, stderr=subprocess.DEVNULL, timeout=10,
                )
                print(output.strip().split()[-1].removeprefix('v'))
                raise SystemExit(0)
    except (OSError, subprocess.SubprocessError):
        continue
raise SystemExit(1)
PYVERSION
}

if [ "${1:-}" = "--restart-worker" ]; then
  EXPECTED="$2"
  echo "[$(date -u +%FT%TZ)] [t3-autoupdate] restarting t3; expected=$EXPECTED"
  if ! supervisorctl restart t3; then
    echo "[t3-autoupdate] ERROR: supervisorctl restart failed"
    exit 1
  fi
  # Require two successful checks separated by six seconds, longer than the
  # observed startup failures that Supervisor briefly labelled RUNNING.
  VERIFIED=false
  for i in $(seq 1 12); do
    sleep 2
    ACTIVE="$(running_version 2>/dev/null || true)"
    if [ "$ACTIVE" = "$EXPECTED" ] &&
       supervisorctl status t3 | grep -q 'RUNNING' &&
       curl -fsS --max-time 3 http://127.0.0.1:3773/ -o /dev/null; then
      if [ "$VERIFIED" = true ]; then
        echo "[$(date -u +%FT%TZ)] [t3-autoupdate] verified running server: $ACTIVE"
        exit 0
      fi
      VERIFIED=true
      sleep 6
    else
      VERIFIED=false
    fi
  done
  echo "[t3-autoupdate] ERROR: running server did not stabilize on $EXPECTED"
  supervisorctl status t3 || true
  exit 1
fi

# Read-only mode is useful for checking the running version independently.
if [ "${1:-}" = "--running-version" ]; then
  running_version
  exit $?
fi

FORCE=false
if [ "${1:-}" = "--force" ] || [ "${1:-}" = "-f" ]; then
  FORCE=true
fi
INSTALLED="$(t3 --version 2>/dev/null | awk '{print $2}' | sed 's/^v//')"
LATEST="$(npm view t3 dist-tags.nightly 2>/dev/null | tr -d ' \r\n')"
ACTIVE="$(running_version 2>/dev/null || true)"

if [ -z "$LATEST" ]; then
  echo "[t3-autoupdate] ERROR: could not resolve latest nightly"
  exit 1
fi
echo "[t3-autoupdate] installed=${INSTALLED:-unknown} running=${ACTIVE:-unavailable} latest=$LATEST"
if [ "$INSTALLED" = "$LATEST" ] && [ "$ACTIVE" = "$LATEST" ] &&
   [ "$FORCE" = false ] && supervisorctl status t3 | grep -q 'RUNNING'; then
  echo "[t3-autoupdate] installed and running versions are up to date"
  exit 0
fi
if [ "$INSTALLED" != "$LATEST" ] || [ "$FORCE" = true ]; then
  echo "[t3-autoupdate] installing t3@$LATEST"
  if ! npm install -g "t3@$LATEST"; then
    echo "[t3-autoupdate] ERROR: npm install failed"
    exit 1
  fi
fi

LOGFILE=/var/log/agent-hub/t3-autoupdate.log
if ! touch "$LOGFILE" 2>/dev/null; then
  LOGFILE=/tmp/t3-autoupdate.log
  touch "$LOGFILE" || exit 1
fi
# A separate session survives both terminal teardown and process-group stops.
nohup setsid bash "$0" --restart-worker "$LATEST" </dev/null >>"$LOGFILE" 2>&1 &
disown
echo "[t3-autoupdate] detached restart scheduled; verification result will be logged in $LOGFILE"
