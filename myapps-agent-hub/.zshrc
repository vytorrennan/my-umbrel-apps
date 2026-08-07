export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/.fnm/aliases/default/bin:$HOME/.fnm/current/bin:$HOME/.fnm:/usr/local/bin:/usr/bin:/bin"

if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --use-on-cd --shell zsh 2>/dev/null)"
fi

export HISTCONTROL=ignoreboth
export HISTFILESIZE=100000
export HISTSIZE=50000
export TERM=xterm-256color
export EDITOR=vi

alias c="clear"
alias please="sudo"
alias make="make -j$(nproc)"
alias agent-logs="sudo tail -f /var/log/agent-hub/*.log"

PROMPT='%(?:%F{green}%B➜%b%F{cyan} %~ :%F{red}%B✗%b) %f'
RPROMPT='%F{magenta}%m%f'
