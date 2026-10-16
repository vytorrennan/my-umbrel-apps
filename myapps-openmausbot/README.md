# OpenMausBot for Umbrel

Requires an x86-64 Umbrel. Open the app from Umbrel on port **8798**, select
**Connect this browser**, then **Connect** on the prefilled pairing screen.
Sign in to a provider in Settings and create a bot.

## Supported features

- Chats, bot teams, rooms, coordination, routines, memory, Company Brain,
  files, approvals, usage history, and workspace backup/restore use upstream's
  self-hosted server and web UI.
- Claude Code, Codex, and Grok CLIs are bundled. Other npm-based engines can
  be installed and updated in **Settings → Engines**. Provider accounts and
  API keys are supplied by the user.
- The built-in Chromium browser and its persistent per-bot sessions are included.
- **Local VM** desktops run in a dedicated nested Docker engine. In Settings,
  prepare the desktop image, select shared/per-bot/pool mode, then create a
  desktop. The live viewer is relayed through the app, with WebSocket support.
  Each running desktop can use 4 GiB RAM and 2 CPUs; the initial image download
  and build also require substantial disk and memory.
- Cloud/Boat computers and **Self-hosted VPS** desktops use the upstream
  configuration screens. Docker CLI and OpenSSH are installed for VPS access.
  Set up `/data/.ssh/config`, keys and verified host keys in the terminal first.
  External computers, service accounts and their charges are separate.
- Connected apps through Composio and custom MCP servers use upstream settings.
  Node/npm, Python/venv, uv/uvx, Git, build tools, Docker CLI and SSH are included.
  Install custom tools under `/data` so they survive updates. `/data/.local/bin`
  and `/data/.local/npm/bin` are on PATH.
- **Open terminal** on the setup page opens a browser shell at `/terminal/`.
  It runs as the app user and is available only through Umbrel authentication.
- Paired native clients, other API clients, and secret-authenticated webhooks
  can connect on port **8797**. This listener preserves OpenMausBot authentication
  and blocks the owner-pairing setup and terminal paths. Generate device invites
  in **Settings → Remote access**. A paired browser can use this endpoint too.
- Server-side text-to-speech works with the provider configuration upstream
  requires. Browser microphone features also depend on upstream support,
  permissions and a secure HTTPS browser context.

Host desktop control, native desktop dictation helpers and Electron-only
features require upstream's desktop app. This container does not have access
to the Umbrel host desktop. ARM64 is unavailable because upstream's server and
cloud-home container images currently publish only `linux/amd64`. Enterprise
features remain subject to upstream licensing. Credentials for external services
are not supplied by this package.

## Connections and remote access

The Umbrel login protects port 8798, including `/umbrel-start` and `/terminal/`.
Do not disable its proxy authentication or publish internal port 8080. The
setup page can create owner pairing codes for authenticated Umbrel users.

Port 8797 serves the normal upstream web/API and `/hooks/` endpoints, without
Umbrel login redirects. Every protected API still requires an OpenMausBot
session, and each webhook requires its own upstream secret. There is no owner
bootstrap or terminal on this listener. Backend ports 8799, 8800, 8801, 8802
and Docker port 2375 are never published.

The default advertised client and webhook address is
`http://${DEVICE_DOMAIN_NAME}:8797`. Other devices must resolve that hostname.
For access beyond a trusted LAN, configure an HTTPS reverse proxy or Tailscale
Serve to forward to port 8797. Preserve the Host and forwarding headers, and
support WebSockets and unbuffered event streams. Do not forward the setup
listener to that address.

An administrator can supply `APP_OPENMAUSBOT_PUBLIC_URL` and
`APP_OPENMAUSBOT_WEBHOOK_URL` to Compose for an externally reachable HTTPS
origin. These are optional overrides; custom domains and provider callbacks
still need their DNS/proxy configuration. Configure the public address before
creating webhook URLs or device invitations. Changing it does not rewrite
existing webhook URLs.

## Isolation and persistent data

The app image extends the upstream cloud-home image to add tools and uses its
self-hosted `server-launcher.js`, rather than the cloud supervisor. It does
not require OpenMausBot's hosted control plane. Caddy, the setup service,
terminal and nested Docker daemon share the server's network namespace.

The nested daemon listens on loopback only and manages this app's desktop
containers. It never mounts Umbrel's Docker socket. The nested daemon requires
a privileged container, as in this store's Agent Hub app, and shares Umbrel's
kernel. Grant app and agent administrative access only to trusted users.
The app user can control that daemon and its own desktops. Desktop containers do not receive
the daemon socket or other Umbrel app data.

`${APP_DATA_DIR}/data/home` is `/data` in both the app and nested daemon. This
keeps upstream's absolute workspace bind paths consistent. The app and the Cua
desktop's workspace user both use UID/GID 1000. The pre-start hook migrates
ownership from UID 1001 used by the earlier package. It does not modify files
already owned by other accounts.

`${APP_DATA_DIR}/data/docker` holds nested images and container state. Back up
the whole app data directory while the complete app is stopped, including its
desktops. Restart the complete app through Umbrel, because the services share
one network namespace. Provider credentials, SSH keys, browser sessions and
workspaces under `/data` survive container replacement. Deleting an app's data
or removing a desktop can still delete its disposable container filesystem.

## Updates through Umbrel

Installed apps do **not** follow `latest`, pull GitHub main, or run an automatic
updater. They keep their tested app image until you install an Umbrel update.
Engine CLIs can be updated separately in upstream's Engines settings.

The repository includes `.github/workflows/openmausbot-update.yml`. Once
published and enabled on GitHub, it checks for stable upstream releases daily.
For a new release it resolves the release image digest, checks the source
version, builds the Umbrel image, runs the smoke test including a real Local VM
screenshot, publishes the tested image, and opens a package update PR. It does
not merge the PR or update installed apps. After review and merge, the new
version can be offered through Umbrel's community app store.

GitHub Actions needs write access to contents and pull requests, and the
repository option allowing Actions to create pull requests. Docker Hub publishing
uses the encrypted `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` Actions secrets.
The `vytor/openmausbot` Docker Hub repository must be public so an Umbrel can
pull it without registry credentials. The workflow becomes active after these
files are pushed to the default branch. For initial
publication, run it manually with **rebuild** enabled. For a packaging-only
release, first increment the `-umbrel.N` version consistently in the manifest,
Compose image tags and `upstream.json`.

Maintainer commands from the repository root:

```sh
python3 myapps-openmausbot/scripts/prepare-update.py
python3 myapps-openmausbot/scripts/prepare-update.py --apply
docker build -t docker.io/vytor/openmausbot:VERSION myapps-openmausbot
python3 myapps-openmausbot/scripts/smoke-test.py --desktop
```

Replace `VERSION` with `packageVersion` from `upstream.json`. The first command
only checks. Release preparation pins the upstream base; the workflow pins the
tested final image digest before creating the review PR.

## Validation and sources

`scripts/smoke-test.py` uses temporary app data and its own Compose project.
It tests setup and origin validation, pairing and session reuse, public API
authentication, terminal isolation, webhook routing, installed tools, nested
Docker workspace ownership, and persistence after container recreation.
`--desktop` additionally builds upstream's managed Cua image, starts a desktop,
captures a screenshot and stops it.

An actual umbrelOS installation, remote VPS credentials, paid providers and
external OAuth services require validation on the target installation. Browser
pairing was also checked manually with the real renderer.

Upstream: https://github.com/milind-soni/OpenMausBot

The icon is upstream's `public/app-icon.svg`. Upstream is Apache-2.0 with an
enterprise carve-out and additional third-party notices in `LICENSING.md`,
`NOTICE`, and `third_party/`. Upstream names and mascot retain their trademark
terms. The original source version and image are recorded in `upstream.json`.
