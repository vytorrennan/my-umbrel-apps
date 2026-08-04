#!/usr/bin/env bash
set -e

# Create default .zshrc if missing to prevent zsh-newuser-install prompt
if [ ! -f /home/developer/.zshrc ]; then
  cat <<'EOF' > /home/developer/.zshrc
export PATH="/home/developer/.local/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/usr/local/bin:$PATH"
export TERM=xterm-256color
alias ll='ls -la'
EOF
  chown developer:developer /home/developer/.zshrc
fi

# Ensure developer user owns /home/developer
chown -R developer:developer /home/developer 2>/dev/null || true

# Start Caw as developer user in /home/developer
echo "Starting Caw on port 8080..."
exec su - developer -c 'export HOST=0.0.0.0; export PORT=8080; export TERM=xterm-256color; cd /home/developer; exec /usr/local/bin/caw'
