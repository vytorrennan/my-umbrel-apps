#!/bin/bash
set -eu

mkdir -p /workspace /root

if [ ! -f /root/.bashrc ]; then
  echo '[ -f /etc/bash.bashrc ] && . /etc/bash.bashrc' > /root/.bashrc
fi

export SHELL=/bin/bash
export TERM=xterm-256color
export COLORTERM=truecolor
export PATH=/usr/local/bin:/root/.local/bin:$PATH

ARGS="-W -p 7681"

if [ -n "${TTYD_CREDENTIAL:-}" ]; then
  ARGS="$ARGS -c ${TTYD_CREDENTIAL}"
fi

cd /workspace
exec ttyd $ARGS herdr
