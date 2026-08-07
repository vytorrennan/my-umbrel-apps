FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# System dependencies: build-essential, git, python3 + pip, curl, unzip, fonts,
# process management (supervisord), QR generation (qrencode) and ttyd terminal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    jq \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    qrencode \
    sudo \
    supervisor \
    tar \
    ttyd \
    unzip \
    wget \
    zsh \
    fontconfig \
    fonts-jetbrains-mono \
    && rm -rf /var/lib/apt/lists/*

# Install JetBrains Mono Nerd Font
RUN mkdir -p /usr/local/share/fonts/JetBrainsMono && \
    curl -fsSL https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/JetBrainsMono.zip -o /tmp/jb.zip && \
    unzip -q /tmp/jb.zip -d /usr/local/share/fonts/JetBrainsMono && \
    rm /tmp/jb.zip && \
    fc-cache -f

# Install uv (Python package installer) system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/ 2>/dev/null || true

# Non-root developer user (UID 1000, matching the host) with passwordless sudo
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /usr/bin/zsh -u 1000 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

# Everything user-level runs as developer so files are owned by the non-root user
USER developer
WORKDIR /home/developer

ENV FNM_DIR=/home/developer/.fnm
ENV PATH=/home/developer/.npm-global/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin

# Install fnm and Node.js LTS, then set it as the default
RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /home/developer/.fnm --skip-shell && \
    /home/developer/.fnm/fnm install --lts && \
    /home/developer/.fnm/fnm default lts-latest && \
    node --version && npm --version

# Install the three agent servers as global npm tools (OpenCode, T3 Code, OpenChamber)
# allow-scripts opts npm 11 into running native build scripts (node-pty, msgpackr-extract)
RUN mkdir -p /home/developer/.npm-global && \
    npm config set prefix /home/developer/.npm-global && \
    npm config set allow-scripts=opencode-ai,node-pty,msgpackr-extract --location=user && \
    npm install -g opencode-ai t3@nightly @openchamber/web

# Shell config for the developer user
COPY --chown=developer:developer .zshrc /home/developer/.zshrc
COPY --chown=developer:developer .bashrc /home/developer/.bashrc

# Projects folder (bind-mounted from the host)
RUN mkdir -p /home/developer/Projects

# Root-owned entrypoint and helper scripts
USER root
COPY entrypoint.sh /entrypoint.sh
COPY scripts/pair-t3.sh /usr/local/bin/pair-t3
COPY scripts/set-lan-host.sh /usr/local/bin/set-lan-host
COPY scripts/agent-hub-info.sh /usr/local/bin/agent-hub-info
RUN chmod +x /entrypoint.sh /usr/local/bin/pair-t3 /usr/local/bin/set-lan-host /usr/local/bin/agent-hub-info

EXPOSE 3000 3773 4096 7682

ENTRYPOINT ["/entrypoint.sh"]
