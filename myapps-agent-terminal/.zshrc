# Enable Powerlevel10k instant prompt
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"

ENABLE_CORRECTION="true"
COMPLETION_WAITING_DOTS="true"

plugins=(git fzf zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# Environment variables
export PATH="$HOME/.local/bin:$HOME/.fnm:$HOME/.cargo/bin:$PATH"
export HISTCONTROL=ignoreboth
export HISTFILESIZE=100000
export HISTSIZE=50000

# Fast Node Manager (fnm)
if command -v fnm &> /dev/null; then
  eval "$(fnm env --use-on-cd --shell zsh)"
fi

# Aliases
alias c="clear"
alias make="make -j$(nproc)"
alias please="sudo"

# Powerlevel10k config
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
