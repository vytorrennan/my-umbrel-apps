FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Install system dependencies, build-essential, openssl, git, and python3
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    sudo \
    unzip \
    tar \
    jq \
    procps \
    lsof \
    ca-certificates \
    openssl \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt-get/lists/*

# Delete existing default ubuntu user (UID 1000) and create developer user with passwordless sudo
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /bin/bash -u 1000 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

# Install Antigravity CLI (agy) & Language Server binary
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true && \
    mkdir -p /opt/Antigravity/resources/bin && \
    if [ -f /root/.local/bin/language_server ]; then cp /root/.local/bin/language_server /opt/Antigravity/resources/bin/language_server; fi

# Switch to developer user for Node.js setup
USER developer
WORKDIR /home/developer

ENV FNM_DIR=/home/developer/.fnm
ENV PATH=/home/developer/.local/bin:/home/developer/.fnm/aliases/default/bin:/home/developer/.fnm/current/bin:/home/developer/.fnm:$PATH

# Install fnm & Node LTS
RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /home/developer/.fnm --skip-shell && \
    /home/developer/.fnm/fnm install --lts && \
    /home/developer/.fnm/fnm default lts-latest

# Install Antigravity CLI for developer user as well
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true

# Copy antigravity-client source
RUN git clone https://github.com/jkfujinami/antigravity-client.git /home/developer/antigravity-client
WORKDIR /home/developer/antigravity-client
RUN npm install && npm run build

# Create mount point directories
RUN mkdir -p /home/developer/Projects /home/developer/.config/Antigravity /home/developer/.gemini

USER root

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
