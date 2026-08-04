# Powerlevel10k lean configuration for Agent Terminal
'builtin' 'local' '-a' 'p10k_config_opts'
'builtin' 'local' '-h' 'POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS'
'builtin' 'local' '-h' 'POWERLEVEL9K_LEFT_PROMPT_ELEMENTS'

POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(
  dir                     # current working directory
  vcs                     # git status
  prompt_char             # prompt symbol
)

POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(
  status                  # exit code
  command_execution_time  # duration
  context                 # user@hostname
)

POWERLEVEL9K_MODE='nerdfont-complete'
POWERLEVEL9K_ICON_PADDING=none
POWERLEVEL9K_PROMPT_ADD_NEWLINE=false
POWERLEVEL9K_MULTILINE_FIRST_PROMPT_PREFIX=''
POWERLEVEL9K_MULTILINE_LAST_PROMPT_PREFIX=''

# Directory styling
POWERLEVEL9K_DIR_BACKGROUND='none'
POWERLEVEL9K_DIR_FOREGROUND='cyan'
POWERLEVEL9K_SHORTEN_STRATEGY='truncate_to_unique'

# Prompt char styling
POWERLEVEL9K_PROMPT_CHAR_OK_VIINS_FOREGROUND='green'
POWERLEVEL9K_PROMPT_CHAR_ERROR_VIINS_FOREGROUND='red'
POWERLEVEL9K_PROMPT_CHAR_OK_VIINS_CONTENT_EXPANSION='❯'
POWERLEVEL9K_PROMPT_CHAR_ERROR_VIINS_CONTENT_EXPANSION='❯'
