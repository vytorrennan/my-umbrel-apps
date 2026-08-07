#!/usr/bin/env bash
set -euo pipefail

DEV_HOME=/home/developer
PORT=3773

LAN_HOST="${1:-}"
[ -z "$LAN_HOST" ] && LAN_HOST="${T3_LAN_HOST:-}"
[ -z "$LAN_HOST" ] && [ -f "$DEV_HOME/.config/agent-hub/lan-host" ] && LAN_HOST="$(cat "$DEV_HOME/.config/agent-hub/lan-host")"
if [ -z "$LAN_HOST" ]; then
  LAN_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "Warning: no LAN host configured, using container IP $LAN_HOST." >&2
  echo "This is not reachable from other devices. Run once: set-lan-host <umbrel-ip>" >&2
fi

PAIR_ENV="HOME=$DEV_HOME T3CODE_HOME=$DEV_HOME/.t3 PATH=$DEV_HOME/.npm-global/bin:$DEV_HOME/.fnm/aliases/default/bin:$DEV_HOME/.fnm/current/bin:$DEV_HOME/.fnm:/usr/local/bin:/usr/bin:/bin TERM=xterm-256color"

if [ "$(id -u)" -eq 0 ]; then
  OUT="$(sudo -u developer -- env $PAIR_ENV t3 pair 2>&1)"
else
  OUT="$(env $PAIR_ENV t3 pair 2>&1)"
fi

printf '%s\n' "$OUT"

RAW_URL="$(printf '%s\n' "$OUT" | sed -n 's/^Pairing URL: //p' | tail -1)"
if [ -n "$RAW_URL" ]; then
  URL="$(printf '%s' "$RAW_URL" | sed -E "s#^[^/]+//[^/]+#http://$LAN_HOST:$PORT#")"
  echo ""
  echo "Reachable pairing URL: $URL"
  echo ""
  if command -v qrencode >/dev/null 2>&1; then
    qrencode -t ANSIUTF8 "$URL"
  fi
fi
