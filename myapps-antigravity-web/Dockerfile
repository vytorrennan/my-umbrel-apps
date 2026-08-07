FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Install system dependencies, OpenSSL, Git, Python3, and Node.js 20 system-wide
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

# Install Node.js 20 system-wide
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt-get/lists/*

# Create developer user (UID 1000) with passwordless sudo
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    useradd -m -s /bin/bash -u 1000 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

# Install Antigravity CLI (agy) & copy language_server binary to /opt/Antigravity/resources/bin/
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash || true
RUN mkdir -p /opt/Antigravity/resources/bin
COPY language_server /opt/Antigravity/resources/bin/language_server
RUN chmod +x /opt/Antigravity/resources/bin/language_server

# Clone & Build antigravity-client
WORKDIR /home/developer/antigravity-client
RUN git clone https://github.com/jkfujinami/antigravity-client.git . && \
    npm install && \
    npm run build && \
    chown -R developer:developer /home/developer

# Create mount point directories
RUN mkdir -p /home/developer/Projects /home/developer/.config/Antigravity /home/developer/.gemini && \
    chown -R developer:developer /home/developer

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
