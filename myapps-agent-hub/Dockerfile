FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# System dependencies: build-essential, git, python3 + pip, curl, unzip, fonts,
# process management (supervisord), QR generation (qrencode), docker CLI, and ttyd terminal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    docker.io \
    docker-compose-v2 \
    git \
    jq \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    netcat-openbsd \
    openssh-client \
    qrencode \
    sqlite3 \
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

# Install Tailscale
RUN curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null && \
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends tailscale && \
    rm -rf /var/lib/apt/lists/*

# Install Antigravity CLI (agy) system-wide
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true && \
    cp /root/.local/bin/agy /usr/local/bin/ 2>/dev/null || true

# Non-root developer user (UID 1000, matching the host) with passwordless sudo and docker group
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /usr/bin/zsh -u 1000 -G docker developer && \
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

# Install the four agent servers as global npm tools (OpenCode, T3 Code, OpenChamber,
# and Codex CLI) plus Antigravity CLI (agy). allow-scripts opts npm 11 into
# running native build scripts and selecting OpenCode's platform binary.
ENV OPENCODE_VERSION=2.0.22
ENV OPENCHAMBER_VERSION=2.1.0
RUN mkdir -p /home/developer/.npm-global && \
    npm config set prefix /home/developer/.npm-global && \
    npm config set allow-scripts=@opencode/cli,@openai/codex,node-pty,msgpackr-extract --location=user && \
    npm install -g "@opencode/cli@$OPENCODE_VERSION" t3@nightly "@openchamber/web@$OPENCHAMBER_VERSION" @openai/codex && \
    opencode --version

# Install Antigravity CLI (agy) for the developer user (creates
# ~/.local/bin/agy and ~/.antigravity/bin/run_agy_remote_control.sh)
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true

# Install shell config, entrypoint and helpers together to avoid many small layers.
USER root
COPY .zshrc .bashrc entrypoint.sh scripts/ /tmp/agent-hub-build/
RUN install -o developer -g developer -m 644 /tmp/agent-hub-build/.zshrc /home/developer/.zshrc && \
    install -o developer -g developer -m 644 /tmp/agent-hub-build/.bashrc /home/developer/.bashrc && \
    install -d -o developer -g developer /home/developer/Projects && \
    install -m 755 /tmp/agent-hub-build/entrypoint.sh /entrypoint.sh && \
    for helper in pair-t3 set-lan-host agent-hub-info codex-ssd-guard t3-nightly-autoupdate agent-hub-opencode-v2; do \
      install -m 755 "/tmp/agent-hub-build/$helper.sh" "/usr/local/bin/$helper"; \
    done && \
    rm -rf /tmp/agent-hub-build

EXPOSE 3000 3773 4096 7682

ENTRYPOINT ["/entrypoint.sh"]
