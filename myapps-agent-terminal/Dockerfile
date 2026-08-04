FROM debian:stable-slim

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/root \
    SHELL=/bin/bash \
    TERM=xterm-256color \
    COLORTERM=truecolor \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    HERDR_INSTALL_DIR=/usr/local/bin \
    PATH=/usr/local/bin:/root/.local/bin:$PATH

# --- base packages -----------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git openssh-client \
        procps less nano tini locales bash-completion build-essential \
    && sed -i '/en_US.UTF-8/s/^# //' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# --- sane root shell: color prompt, color ls, tab completion -----------
RUN printf '%s\n' \
    "" \
    "alias ls='ls --color=auto'" \
    "alias ll='ls -alF --color=auto'" \
    "alias grep='grep --color=auto'" \
    "export TERM=xterm-256color" \
    "export COLORTERM=truecolor" \
    "export PATH=/usr/local/bin:/root/.local/bin:\$PATH" \
    "PS1='\[\033[01;32m\]\u@agent-terminal\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '" \
    "if [ -f /etc/bash_completion ] && ! shopt -oq posix; then" \
    "  . /etc/bash_completion" \
    "fi" \
    >> /etc/bash.bashrc

# --- Node.js 22 (required by Codex CLI / Antigravity CLI) --------------
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- ttyd (browser terminal, wraps xterm.js over websockets) -----------
RUN ARCH="$(dpkg --print-architecture)" \
    && case "$ARCH" in \
         amd64)  TTYD_ARCH="x86_64" ;; \
         arm64)  TTYD_ARCH="aarch64" ;; \
         *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.${TTYD_ARCH}" \
         -o /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd

# --- Herdr (agent-aware terminal multiplexer) ---------------------------
RUN curl -fsSL https://herdr.dev/install.sh | sh

# --- Codex CLI (OpenAI) --------------------------------------------------
RUN npm install -g @openai/codex

# --- Antigravity CLI (Google) --------------------------------------------
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && cp -f /root/.local/bin/agy /usr/local/bin/agy 2>/dev/null || true

WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 7681

ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint.sh"]
