#!/usr/bin/env bash
set -e

# Ensure permissions on developer home directory and Projects
chown -R developer:developer /home/developer 2>/dev/null || true

# Start ttyd serving Herdr interactive terminal as developer user
echo "Starting Agent Terminal on port 7681..."
exec su - developer -c 'export TERM=xterm-256color; ttyd -p 7681 -W -i 0.0.0.0 zsh -ic "herdr"'
