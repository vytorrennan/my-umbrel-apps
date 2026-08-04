# Enable Powerlevel10k instant prompt
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"

ENABLE_CORRECTION="true"
COMPLETION_WAITING_DOTS="true"

# Disable omz fzf plugin auto-sourcing to avoid debian path notice
DISABLE_FZF_AUTO_COMPLETION="true"
DISABLE_FZF_KEY_BINDINGS="true"

plugins=(git zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# Environment variables & PATH
export PATH="$HOME/.local/bin:$HOME/.fnm/aliases/default/bin:$HOME/.fnm/current/bin:$HOME/.fnm:$PATH"
export HISTCONTROL=ignoreboth
export HISTFILESIZE=100000
export HISTSIZE=50000
export TERM=xterm-256color

# Fast Node Manager (fnm)
if command -v fnm &> /dev/null; then
  eval "$(fnm env --use-on-cd --shell zsh 2>/dev/null)"
fi

# Modern fzf integration
if command -v fzf &> /dev/null; then
  eval "$(fzf --zsh 2>/dev/null)" || true
fi

# Aliases
alias c="clear"
alias make="make -j$(nproc)"
alias please="sudo"

# Powerlevel10k config
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
