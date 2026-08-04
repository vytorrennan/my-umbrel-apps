FROM debian:stable-slim

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/root \
    HERDR_INSTALL_DIR=/usr/local/bin \
    PATH=/usr/local/bin:/root/.local/bin:$PATH

# --- base packages -----------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git openssh-client \
        procps less nano tini build-essential\
    && rm -rf /var/lib/apt/lists/*

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
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash

WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 7681

ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint.sh"]
