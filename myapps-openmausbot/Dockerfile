ARG UPSTREAM_IMAGE=ghcr.io/milind-soni/openmausbot-cloud-home@sha256:ccba415571d7957cd1bc53c94c938ffa88d52de0331f6ccea986b5697136563c
FROM docker:29-cli@sha256:1a4c7cb63513f349bdad01fcc6e0f3f2f67d37b9da86f14dc0d4a0942eecda00 AS docker_cli
FROM ghcr.io/astral-sh/uv@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv
FROM ${UPSTREAM_IMAGE}

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential openssh-client pkg-config python3 python3-pip python3-venv \
      unzip xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && userdel node && if getent group node >/dev/null; then groupdel node; fi \
    && groupmod -g 1000 maus && usermod -u 1000 -g 1000 maus \
    && chown 1000:1000 /data
# Cua desktop workspaces belong to UID 1000. Match it in the app container so
# the upstream 0700 workspace permissions work in both containers.
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
COPY --from=uv /uv /uvx /usr/local/bin/
RUN curl -fsSL https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 -o /usr/local/bin/ttyd \
    && echo '8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55  /usr/local/bin/ttyd' | sha256sum -c - \
    && chmod 0755 /usr/local/bin/ttyd
ENV PATH=/data/.local/bin:/data/.local/npm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    NPM_CONFIG_PREFIX=/data/.local/npm \
    SHELL=/bin/bash
USER maus
CMD ["node", "/app/dist-server/server-launcher.js"]
