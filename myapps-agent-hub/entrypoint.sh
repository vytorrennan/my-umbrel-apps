#!/usr/bin/env bash
set -euo pipefail

DEV_HOME=/home/developer
CFG_DIR="$DEV_HOME/.config/agent-hub"
SECRETS="$CFG_DIR/secrets.env"
LOG_DIR=/var/log/agent-hub
SUPERVISOR_CONF=/etc/supervisor/supervisord.conf

DEV_PATH="$DEV_HOME/.npm-global/bin:$DEV_HOME/.fnm/aliases/default/bin:$DEV_HOME/.fnm/current/bin:$DEV_HOME/.fnm:$DEV_HOME/.local/bin:$DEV_HOME/Android/Sdk/platform-tools:$DEV_HOME/Android/Sdk/emulator:/usr/local/bin:/usr/bin:/bin"
DOCKER_HOST="${DOCKER_HOST:-tcp://dind:2375}"

# ---------------------------------------------------------------------------
# 1. Make sure the data volume is owned by the non-root developer user.
#    NOTE: never recurse into /home/developer/Projects - it is a bind mount of
#    the host's Projects folder.
# ---------------------------------------------------------------------------
chown developer:developer "$DEV_HOME" 2>/dev/null || true
install -d -o developer -g developer "$CFG_DIR" "$DEV_HOME/.local/share" "$DEV_HOME/.local/state" "$DEV_HOME/.cache" 2>/dev/null || true
# The SDK facade exposes only the managed DinD phone to T3. No downloads or boot.
su developer -s /bin/bash -c '/usr/local/bin/agent-hub-android install-facade'
chown developer:developer "$DEV_HOME/.zshrc" "$DEV_HOME/.bashrc" 2>/dev/null || true
# The home volume preserves older shell configs across image rebuilds.
# Load the completion package bundled in the image for existing Bash terminals.
if [ -f "$DEV_HOME/.bashrc" ] && ! grep -q '^# Enable completion for command wrappers' "$DEV_HOME/.bashrc"; then
  cat >> "$DEV_HOME/.bashrc" <<'BASH_COMPLETION'

# Enable completion for command wrappers such as sudo in non-login terminals.
if [[ $- == *i* ]] && ! declare -F _init_completion >/dev/null && \
   [[ -r /usr/share/bash-completion/bash_completion ]]; then
  . /usr/share/bash-completion/bash_completion
fi
BASH_COMPLETION
fi

mkdir -p "$LOG_DIR"
touch "$LOG_DIR/t3-autoupdate.log" 2>/dev/null || true
chown developer:developer "$LOG_DIR/t3-autoupdate.log" 2>/dev/null || true

# Install the window starter on every boot; its schedule stays in the home volume.
WINDOW_STARTER_DIR="$DEV_HOME/.local/share/codex-window-starter"
install -d -o developer -g developer "$WINDOW_STARTER_DIR" "$WINDOW_STARTER_DIR/empty"
install -o developer -g developer -m 755 \
  /usr/local/lib/agent-hub/codex-window-starter.py "$WINDOW_STARTER_DIR/starter.py"
touch "$WINDOW_STARTER_DIR/service.log"
chown developer:developer "$WINDOW_STARTER_DIR/service.log"

# T3 imports a login-shell PATH, which can discard its Supervisor PATH prefix.
# Keep the npm bridge in the existing home bin directory used by that shell.
install -d -o developer -g developer "$DEV_HOME/.local/bin"
NPM_BRIDGE="$DEV_HOME/.local/bin/npm"
if [ -e "$NPM_BRIDGE" ] || [ -L "$NPM_BRIDGE" ]; then
  if ! grep -q 'Forward npm; wait for the shared server' "$NPM_BRIDGE" 2>/dev/null && \
     [ ! -e "$NPM_BRIDGE.before-t3-update-bridge" ] && [ ! -L "$NPM_BRIDGE.before-t3-update-bridge" ]; then
    cp -a "$NPM_BRIDGE" "$NPM_BRIDGE.before-t3-update-bridge"
  fi
  rm -f "$NPM_BRIDGE"
fi
install -o developer -g developer -m 755 \
  /usr/local/lib/agent-hub/provider-bin/npm "$NPM_BRIDGE"

# Ensure DOCKER_HOST points to dind in shell rc files and system environment
sed -i 's|tcp://127.0.0.1:2375|tcp://dind:2375|g' "$DEV_HOME/.bashrc" "$DEV_HOME/.zshrc" 2>/dev/null || true
if [ -f "$DEV_HOME/.bashrc" ] && ! grep -q "DOCKER_HOST" "$DEV_HOME/.bashrc" 2>/dev/null; then
  echo 'export DOCKER_HOST="${DOCKER_HOST:-tcp://dind:2375}"' >> "$DEV_HOME/.bashrc"
fi
if [ -f "$DEV_HOME/.zshrc" ] && ! grep -q "DOCKER_HOST" "$DEV_HOME/.zshrc" 2>/dev/null; then
  echo 'export DOCKER_HOST="${DOCKER_HOST:-tcp://dind:2375}"' >> "$DEV_HOME/.zshrc"
fi
# Keep the owner's Claude alias available in retained and fresh homes.
for shell_rc in "$DEV_HOME/.bashrc" "$DEV_HOME/.zshrc"; do
  if ! grep -q '^alias claude=' "$shell_rc" 2>/dev/null; then
    echo 'alias claude="claude --dangerously-skip-permissions"' >> "$shell_rc"
    chown developer:developer "$shell_rc"
  fi
done

if [ -f "$DEV_HOME/.bashrc" ] && ! grep -q "alias agy=" "$DEV_HOME/.bashrc" 2>/dev/null; then
  echo 'alias agy="agy --dangerously-skip-permissions"' >> "$DEV_HOME/.bashrc"
fi
if [ -f "$DEV_HOME/.zshrc" ] && ! grep -q "alias agy=" "$DEV_HOME/.zshrc" 2>/dev/null; then
  echo 'alias agy="agy --dangerously-skip-permissions"' >> "$DEV_HOME/.zshrc"
fi
echo "DOCKER_HOST=$DOCKER_HOST" > /etc/environment 2>/dev/null || true

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
# Reuse the saved JWT as well as the password when recreating the container.
JWT="${OPENCODE_JWT_SECRET:-$JWT}"

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
# 3b. Persist Tailscale state & SSH host keys across container updates.
#     /var/lib/tailscale contains tailscaled.state (machine auth/node key)
#     and /var/lib/tailscale/ssh/ (host keys for Tailscale SSH).
# ---------------------------------------------------------------------------
TAILSCALE_STATE_DIR="$CFG_DIR/tailscale"
mkdir -p "$TAILSCALE_STATE_DIR"
chmod 700 "$TAILSCALE_STATE_DIR"

if [ ! -L /var/lib/tailscale ]; then
  if [ -d /var/lib/tailscale ] && [ ! -e "$TAILSCALE_STATE_DIR/tailscaled.state" ]; then
    cp -a /var/lib/tailscale/. "$TAILSCALE_STATE_DIR/" 2>/dev/null || true
  fi
  rm -rf /var/lib/tailscale
  ln -s "$TAILSCALE_STATE_DIR" /var/lib/tailscale
fi

# Also persist OpenSSH server host keys if any exist
SSH_HOST_KEYS_DIR="$CFG_DIR/ssh_host_keys"
mkdir -p "$SSH_HOST_KEYS_DIR"
chmod 700 "$SSH_HOST_KEYS_DIR"
for key in /etc/ssh/ssh_host_*_key*; do
  if [ -f "$key" ]; then
    fname="$(basename "$key")"
    if [ ! -f "$SSH_HOST_KEYS_DIR/$fname" ]; then
      cp -a "$key" "$SSH_HOST_KEYS_DIR/$fname" 2>/dev/null || true
    fi
  fi
done
for key in "$SSH_HOST_KEYS_DIR"/ssh_host_*_key*; do
  if [ -f "$key" ]; then
    fname="$(basename "$key")"
    cp -a "$key" "/etc/ssh/$fname" 2>/dev/null || true
  fi
done

# ---------------------------------------------------------------------------
# 4. Supervisor config for the services, all running as developer (t3,
#    opencode, tailscaled and optional Android bridge).
# ---------------------------------------------------------------------------
# The home volume can hide the npm packages bundled in a rebuilt image.
# Upgrade old persisted installations before either server opens the database.
su developer -s /bin/bash -c 'exec /usr/local/bin/agent-hub-opencode-v2'
# Retained home volumes can hide CLI packages installed in the new image.
su developer -s /bin/bash -c "export PATH='$DEV_PATH'; command -v claude >/dev/null || npm install -g --allow-scripts=@anthropic-ai/claude-code @anthropic-ai/claude-code"
# T3 uses the supervised server below. Do not let routine CLI commands create
# a second, persistent managed service. Preserve all other service settings.
su developer -s /bin/bash -c "export PATH='$DEV_PATH'; opencode service set disabled true"

# Docker blocks the user namespaces Chrome's sandbox needs. Use T3's supported
# setting to run its browser inside the container without Chrome's sandbox.
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
command=t3 serve --host 0.0.0.0 --port 3773 --base-dir $DEV_HOME/.t3 --tailscale-serve --tailscale-serve-port 443
user=developer
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/t3.log
environment=PATH="/usr/local/lib/agent-hub/provider-bin:$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",FNM_DIR="$DEV_HOME/.fnm",T3CODE_HOME="$DEV_HOME/.t3",T3CODE_SERVER_BROWSER_SANDBOX="0",DOCKER_HOST="$DOCKER_HOST",ANDROID_HOME="$DEV_HOME/Android/Sdk"

[program:opencode]
command=/usr/bin/python3 /usr/local/bin/agent-hub-opencode-server -- opencode serve --port 4096 --hostname 0.0.0.0 --print-logs
user=developer
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stopwaitsecs=15
redirect_stderr=true
stdout_logfile=$LOG_DIR/opencode.log
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",TERM="xterm-256color",OPENCODE_SERVER_PASSWORD="$PW",OPENCODE_SERVER_USERNAME="opencode",DOCKER_HOST="$DOCKER_HOST"

[program:tailscaled]
command=/usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/tailscaled.log


[program:tailscale-maintenance]
command=/usr/bin/python3 /usr/local/bin/agent-hub-tailscale-maintenance
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/agent-hub/tailscale-maintenance.log

[program:codex-window-starter]
command=/usr/bin/python3 $WINDOW_STARTER_DIR/starter.py
directory=$WINDOW_STARTER_DIR/empty
user=developer
autostart=true
autorestart=true
startsecs=5
startretries=3
stopasgroup=true
killasgroup=true
stopwaitsecs=10
redirect_stderr=true
stdout_logfile=$WINDOW_STARTER_DIR/service.log
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=2
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",PYTHONUNBUFFERED="1"

# No SDK downloads or emulator startup on fresh installations. This reconnects
# only installations explicitly enabled by agent-hub-android setup/start.
[program:android-adb]
command=/usr/local/bin/agent-hub-android bridge
user=developer
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/android-adb.log
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=2
environment=PATH="$DEV_PATH",HOME="$DEV_HOME",DOCKER_HOST="$DOCKER_HOST",PYTHONUNBUFFERED="1"
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
echo "  OpenCode web   : http://$LAN_HOST:4096"
echo "  T3 Code        : http://$LAN_HOST:3773  (pair with a token)"
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
