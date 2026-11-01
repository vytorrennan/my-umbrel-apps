FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libasound2t64 libdbus-1-3 libfontconfig1 libgl1 libnss3 \
    libpulse0 libvulkan1 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxext6 libxfixes3 libxi6 libxkbcommon0 libxrandr2 \
    libxrender1 libxtst6 socat python3 \
    && rm -rf /var/lib/apt/lists/*
RUN (userdel -r ubuntu 2>/dev/null || true) && useradd -m -u 1000 developer
COPY --chmod=755 entrypoint.sh /android-entrypoint.sh
ENTRYPOINT ["/android-entrypoint.sh"]
