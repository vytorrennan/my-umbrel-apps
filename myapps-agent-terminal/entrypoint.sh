#!/usr/bin/env bash
set -e

# Ensure permissions on developer home directory and Projects
chown -R developer:developer /home/developer 2>/dev/null || true

# Start ttyd serving Herdr interactive terminal as developer user with modern theme
echo "Starting Agent Terminal on port 7681..."
exec su - developer -c 'export TERM=xterm-256color; exec ttyd -p 7681 -W -i 0.0.0.0 \
  -t fontSize=15 \
  -t fontFamily="\"Fira Code\", \"JetBrains Mono\", monospace" \
  -t cursorBlink=true \
  -t cursorStyle=bar \
  -t theme="{\"background\": \"#0e131f\", \"foreground\": \"#e2e8f0\", \"cursor\": \"#38bdf8\", \"cursorAccent\": \"#0e131f\", \"selectionBackground\": \"#1e293b\", \"black\": \"#0e131f\", \"red\": \"#ef4444\", \"green\": \"#10b981\", \"yellow\": \"#f59e0b\", \"blue\": \"#3b82f6\", \"magenta\": \"#d946ef\", \"cyan\": \"#06b6d4\", \"white\": \"#f8fafc\", \"brightBlack\": \"#475569\", \"brightRed\": \"#f87171\", \"brightGreen\": \"#34d399\", \"brightYellow\": \"#fbbf24\", \"brightBlue\": \"#60a5fa\", \"brightMagenta\": \"#e879f9\", \"brightCyan\": \"#22d3ee\", \"brightWhite\": \"#ffffff\"}" \
  zsh -ic "herdr"'
