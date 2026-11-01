export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/.fnm/aliases/default/bin:$HOME/.fnm/current/bin:$HOME/.fnm:/usr/local/bin:/usr/bin:/bin"

if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd 2>/dev/null)"
fi

export TERM=xterm-256color
export EDITOR=vi
export DOCKER_HOST="${DOCKER_HOST:-tcp://dind:2375}"

# Enable completion for command wrappers such as sudo in non-login terminals.
if [[ $- == *i* ]] && ! declare -F _init_completion >/dev/null && \
   [[ -r /usr/share/bash-completion/bash_completion ]]; then
  . /usr/share/bash-completion/bash_completion
fi

alias c="clear"
alias please="sudo"
alias make="make -j$(nproc)"
alias agent-logs="sudo tail -f /var/log/agent-hub/*.log"
alias agy="agy --dangerously-skip-permissions"

# Codex SSD-wear guard: redirect log DB to RAM + block runaway inserts.
[ -x /usr/local/bin/codex-ssd-guard ] && /usr/local/bin/codex-ssd-guard >/dev/null 2>&1

# Claude Code default permissions mode
alias claude='claude --dangerously-skip-permissions'
