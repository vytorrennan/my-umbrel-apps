# Stage 1: Build Frontend
FROM node:22-bookworm AS frontend-builder
WORKDIR /app
RUN git clone --depth=1 https://github.com/04mg/caw .
COPY patch_terminal.py /tmp/patch_terminal.py
RUN python3 /tmp/patch_terminal.py
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

# Install system dependencies, build-essential, fontconfig
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
    fonts-jetbrains-mono \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt-get/lists/*

# Install JetBrains Mono Nerd Font
RUN mkdir -p /usr/local/share/fonts/JetBrainsMono && \
    curl -fsSL https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/JetBrainsMono.zip -o /tmp/jb.zip && \
    unzip -q /tmp/jb.zip -d /usr/local/share/fonts/JetBrainsMono && \
    rm /tmp/jb.zip && \
    fc-cache -f

# Delete default ubuntu user (UID 1000) and create developer user with passwordless sudo
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /usr/bin/zsh -u 1000 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

# Install Herdr CLI system-wide
RUN curl -fsSL https://herdr.dev/install.sh | sh || true && \
    cp /root/.local/bin/herdr /usr/local/bin/ 2>/dev/null || true

# Install Antigravity CLI (agy) system-wide
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true && \
    cp /root/.local/bin/agy /usr/local/bin/ 2>/dev/null || true

# Install uv (Python package installer) system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | sh || true && \
    cp /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/ 2>/dev/null || true

# Switch to developer user for Node.js, fnm, npm packages, oh-my-zsh setup
USER developer
WORKDIR /home/developer

# Setup fnm environment paths for developer user
ENV FNM_DIR=/home/developer/.fnm
ENV PATH=/home/developer/.local/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:$PATH

# Install fnm & Node LTS & set default
RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /home/developer/.fnm --skip-shell && \
    /home/developer/.fnm/fnm install --lts && \
    /home/developer/.fnm/fnm default lts-latest && \
    npm install -g @openai/codex || true

# Install Oh My Zsh & plugins for developer user
RUN git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git /home/developer/.oh-my-zsh && \
    git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions /home/developer/.oh-my-zsh/custom/plugins/zsh-autosuggestions && \
    git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting /home/developer/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting && \
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/developer/.oh-my-zsh/custom/themes/powerlevel10k

# Copy Zsh configs for developer user
COPY --chown=developer:developer .zshrc /home/developer/.zshrc
COPY --chown=developer:developer .p10k.zsh /home/developer/.p10k.zsh

# Also run user-level CLI installers for developer user
RUN curl -fsSL https://herdr.dev/install.sh | sh || true
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true
RUN curl -LsSf https://astral.sh/uv/install.sh | sh || true

RUN mkdir -p /home/developer/Projects

USER root

# Copy templates to /etc/skel/ so entrypoint can auto-heal existing persistent volumes
COPY .zshrc /etc/skel/.zshrc
COPY .p10k.zsh /etc/skel/.p10k.zsh

# Copy caw binary from backend-builder
COPY --from=backend-builder /caw /usr/local/bin/caw
RUN chmod +x /usr/local/bin/caw

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
