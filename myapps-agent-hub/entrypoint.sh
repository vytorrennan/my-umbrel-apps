#!/usr/bin/env bash
set -euo pipefail

DEV_HOME=/home/developer
CFG_DIR="$DEV_HOME/.config/agent-hub"
SECRETS="$CFG_DIR/secrets.env"
LOG_DIR=/var/log/agent-hub
SUPERVISOR_CONF=/etc/supervisor/supervisord.conf

DEV_PATH="$DEV_HOME/.npm-global/bin:$DEV_HOME/.fnm/aliases/default/bin:$DEV_HOME/.fnm/current/bin:$DEV_HOME/.fnm:$DEV_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

# ---------------------------------------------------------------------------
# 1. Make sure the data volume is owned by the non-root developer user.
#    NOTE: never recurse into /home/developer/Projects - it is a bind mount of
#    the host's Projects folder.
# ---------------------------------------------------------------------------
chown developer:developer "$DEV_HOME" 2>/dev/null || true
install -d -o developer -g developer "$CFG_DIR" "$DEV_HOME/.local/share" "$DEV_HOME/.local/state" "$DEV_HOME/.cache" 2>/dev/null || true
chown developer:developer "$DEV_HOME/.zshrc" "$DEV_HOME/.bashrc" 2>/dev/null || true
mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# 2. Persisted secrets: shared UI/API password and OpenCode JWT secret.
#    Persisted across restarts so sessions survive. Password is alphanumeric so
#    it is safe inside the supervisor config.
# ---------------------------------------------------------------------------
PW=""
JWT=""
if [ -f "$SECRETS" ]; then
  # shellcheck disable=SC1090
  source "$SECRETS" 2>/dev/null || true
fi

if [ -n "${AGENT_PASSWORD:-}" ]; then
  PW="$(printf '%s' "$AGENT_PASSWORD" | tr -cd 'A-Za-z0-9' | head -c 32)"
fi
[ -z "$PW" ] && PW="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
[ -z "$JWT" ] && JWT="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 48)"

umask 077
cat > "$SECRETS" <<EOF
AGENT_PASSWORD=$PW
OPENCODE_JWT_SECRET=$JWT
EOF
chown developer:developer "$SECRETS"
chmod 600 "$SECRETS"

# ---------------------------------------------------------------------------
# 3. Persist the Umbrel LAN host if provided via the T3_LAN_HOST env var.
# ---------------------------------------------------------------------------
if [ -n "${T3_LAN_HOST:-}" ]; then
  printf '%s\n' "$T3_LAN_HOST" > "$CFG_DIR/lan-host"
  chown developer:developer "$CFG_DIR/lan-host"
fi

# ---------------------------------------------------------------------------
# 4. Supervisor config for the four services, all running as developer.
# ---------------------------------------------------------------------------
cat > "$SUPERVISOR_CONF" <<EOF
[unix_http_server]
file=/var/run/supervisor.sock
chmod=0777

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisord]
nodaemon=true
user=root
logfile=$LOG_DIR/supervisord.log
logfile_maxbytes=0
pidfile=/var/run/supervisord.pid

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[program:t3]
command=t3 connect link
user=developer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/t3.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",FNM_DIR="$DEV_HOME/.fnm",T3CODE_HOME="$DEV_HOME/.t3"

[program:t3]
command=t3 serve --host 0.0.0.0 --port 3773 --base-dir $DEV_HOME/.t3
user=developer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/t3.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",FNM_DIR="$DEV_HOME/.fnm",T3CODE_HOME="$DEV_HOME/.t3"

[program:opencode]
command=opencode web --port 4096 --hostname 0.0.0.0 --print-logs
user=developer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/opencode.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",OPENCODE_SERVER_PASSWORD="$PW",OPENCODE_SERVER_USERNAME="opencode"

[program:openchamber]
command=openchamber serve --port 3000 --host 0.0.0.0 --foreground
user=developer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/openchamber.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",OPENCHAMBER_UI_PASSWORD="$PW",OPENCODE_HOST="http://127.0.0.1:4096",OPENCODE_SKIP_START="true",OPENCODE_SERVER_PASSWORD="$PW",OPENCODE_SERVER_USERNAME="opencode",OPENCODE_JWT_SECRET="$JWT"

[program:ttyd]
command=ttyd -p 7682 -W -i 0.0.0.0 -t fontSize=14 -t fontFamily="JetBrainsMono Nerd Font, JetBrains Mono, monospace" -t cursorBlink=true -t cursorStyle=bar -t theme="{\"background\": \"#0e131f\", \"foreground\": \"#e2e8f0\", \"cursor\": \"#38bdf8\", \"cursorAccent\": \"#0e131f\", \"selectionBackground\": \"#1e293b\", \"black\": \"#0e131f\", \"red\": \"#ef4444\", \"green\": \"#10b981\", \"yellow\": \"#f59e0b\", \"blue\": \"#3b82f6\", \"magenta\": \"#d946ef\", \"cyan\": \"#06b6d4\", \"white\": \"#f8fafc\", \"brightBlack\": \"#475569\", \"brightRed\": \"#f87171\", \"brightGreen\": \"#34d399\", \"brightYellow\": \"#fbbf24\", \"brightBlue\": \"#60a5fa\", \"brightMagenta\": \"#e879f9\", \"brightCyan\": \"#22d3ee\", \"brightWhite\": \"#ffffff\"}" zsh
user=developer
directory=/home/developer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/ttyd.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color"
EOF

# ---------------------------------------------------------------------------
# 5. Startup banner (shown in docker logs).
# ---------------------------------------------------------------------------
LAN_HOST="${T3_LAN_HOST:-}"
[ -z "$LAN_HOST" ] && [ -f "$CFG_DIR/lan-host" ] && LAN_HOST="$(cat "$CFG_DIR/lan-host")"
[ -z "$LAN_HOST" ] && LAN_HOST="<umbrel-lan-ip>"

echo ""
echo "================================================================"
echo "  Agent Hub is starting"
echo "----------------------------------------------------------------"
echo "  OpenChamber UI : http://$LAN_HOST:3000"
echo "  OpenCode web   : http://$LAN_HOST:4096"
echo "  T3 Code        : http://$LAN_HOST:3773  (pair with a token)"
echo "  Terminal       : http://$LAN_HOST:7682"
echo ""
echo "  UI/API password : $PW"
echo "  Saved to         : $CFG_DIR/secrets.env"
echo ""
echo "  In the terminal run:"
echo "    agent-hub-info             connection info + password"
echo "    set-lan-host <ip>          remember your Umbrel LAN address"
echo "    pair-t3                    fresh T3 Code pairing QR + URL"
echo "  Logs: sudo tail -f $LOG_DIR/*.log"
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# 6. Run supervisord in the foreground (this keeps the container alive).
# ---------------------------------------------------------------------------
exec supervisord -n -c "$SUPERVISOR_CONF"
