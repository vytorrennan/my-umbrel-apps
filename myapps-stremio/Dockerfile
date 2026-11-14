# Stremio for Umbrel: the open-source stremio-web UI plus the official
# streaming server (server.js), served from one origin by Caddy.
#
# Bump these to update. The server checksum must match the downloaded file.
ARG STREMIO_WEB_REF=v5.1.0
ARG STREMIO_SERVER_VERSION=v4.22.4
ARG STREMIO_SERVER_SHA256=0b5b0bfc0165dad7f6397335594050832aa5760d7098123f739292efb80794ba

# ---- Build the web UI ----------------------------------------------------
FROM node:22-bookworm-slim AS web
ARG STREMIO_WEB_REF
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
# webpack names the asset folder after `git rev-parse HEAD`, so keep .git.
RUN git clone --depth 1 --branch "${STREMIO_WEB_REF}" https://github.com/Stremio/stremio-web.git .
RUN pnpm install --frozen-lockfile && pnpm build && git rev-parse HEAD > /web-commit

# ---- Runtime ---------------------------------------------------------------
FROM node:22-bookworm-slim
ARG STREMIO_SERVER_VERSION
ARG STREMIO_SERVER_SHA256

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl procps \
        i965-va-driver \
    && rm -rf /var/lib/apt/lists/*

COPY --from=caddy:2.10.2 /usr/bin/caddy /usr/bin/caddy

RUN mkdir -p /opt/stremio-server \
    && curl -fsSL "https://dl.strem.io/server/${STREMIO_SERVER_VERSION}/desktop/server.js" \
        -o /opt/stremio-server/server.js \
    && echo "${STREMIO_SERVER_SHA256}  /opt/stremio-server/server.js" | sha256sum -c -

COPY --from=web /src/build /srv/stremio-web
COPY --from=web /web-commit /etc/stremio-web-commit
COPY Caddyfile /etc/caddy/Caddyfile
# The UI's assets live under /<commit>/; route that exact folder to the UI so
# it can't collide with the server's /<infoHash>/<fileIdx> torrent routes.
# Modes are set explicitly so the build doesn't depend on local file modes.
RUN chmod 755 /etc/caddy && chmod 644 /etc/caddy/Caddyfile \
    && sed -i "s/__WEB_COMMIT__/$(cat /etc/stremio-web-commit)/" /etc/caddy/Caddyfile \
    && caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

# Server settings and torrent cache. Created here so a fresh named volume
# inherits the node user's ownership.
RUN mkdir -p /home/node/.stremio-server && chown -R node:node /home/node/.stremio-server

# The wrapper enables GPU (VAAPI) encoding on Intel GPUs that can't decode
# HEVC. i965-va-driver covers older Intel GPUs (up to Coffee Lake).
COPY --chmod=755 ffmpeg-wrapper.sh /usr/local/bin/stremio-ffmpeg
COPY --chmod=755 start-server.sh /usr/local/bin/stremio-server

ENV FFMPEG_BIN=/usr/local/bin/stremio-ffmpeg \
    FFPROBE_BIN=/usr/bin/ffprobe

USER node
WORKDIR /home/node
EXPOSE 8080 11470

# Default: the streaming server. docker-compose runs Caddy from the same image.
CMD ["/usr/local/bin/stremio-server"]
