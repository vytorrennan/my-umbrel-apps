# Stage 1: Build Frontend
FROM node:22-bookworm AS frontend-builder
WORKDIR /app
RUN git clone --depth=1 https://github.com/04mg/caw .
# Patch terminalRegistry.ts to enable auto-copying on text selection & rightClickSelectsWord
RUN python3 -c "path='src/frontend/src/features/terminal/services/terminalRegistry.ts'; code=open(path).read(); code=code.replace('theme,\n  })', 'theme, rightClickSelectsWord: true,\n  })\n  term.onSelectionChange(() => { const sel = term.getSelection(); if (sel && navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(sel).catch(() => {}); } })'); open(path, 'w').write(code)"
RUN cd src/frontend && npm ci && npm run build

# Stage 2: Build Go Backend
FROM golang:1.25-bookworm AS backend-builder
WORKDIR /app
COPY --from=frontend-builder /app /app
RUN cd src && CGO_ENABLED=0 go build -ldflags="-s -w" -o /caw ./cmd/caw

# Stage 3: Runtime Environment
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Install system tools, dev tools, git, zsh, node, python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    zsh \
    sudo \
    unzip \
    tar \
    jq \
    fzf \
    procps \
    ca-certificates \
    fontconfig \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt-get/lists/*

# Delete default ubuntu user (UID 1000) if exists and create developer user with passwordless sudo
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /usr/bin/zsh -u 1000 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

# Create default .zshrc to prevent zsh-newuser-install prompt
RUN echo 'export PATH="/home/developer/.local/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/usr/local/bin:$PATH"' > /home/developer/.zshrc && \
    echo 'export TERM=xterm-256color' >> /home/developer/.zshrc && \
    echo 'alias ll="ls -la"' >> /home/developer/.zshrc && \
    chown developer:developer /home/developer/.zshrc

# Install Antigravity CLI (agy) system-wide
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true && \
    cp /root/.local/bin/agy /usr/local/bin/ 2>/dev/null || true

# Install uv (Python package installer) system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | sh || true && \
    cp /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/ 2>/dev/null || true

# Setup Node.js & fnm for developer user
USER developer
WORKDIR /home/developer
ENV FNM_DIR=/home/developer/.fnm
ENV PATH=/home/developer/.local/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:$PATH

RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /home/developer/.fnm --skip-shell && \
    /home/developer/.fnm/fnm install --lts && \
    /home/developer/.fnm/fnm default lts-latest && \
    npm install -g @openai/codex || true

RUN mkdir -p /home/developer/Projects

USER root

# Copy caw binary from backend-builder
COPY --from=backend-builder /caw /usr/local/bin/caw
RUN chmod +x /usr/local/bin/caw

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
