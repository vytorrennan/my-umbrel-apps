# Agent Terminal (Umbrel community app)

A browser terminal (ttyd + xterm.js) that opens straight into
[Herdr](https://herdr.dev), with [Codex CLI](https://www.npmjs.com/package/@openai/codex)
and [Antigravity CLI](https://antigravity.google) pre-installed so you can
run them as Herdr panes.

## 1. Install into Umbrel

1. Create your own community app store repo from Umbrel's template:
   `github.com/getumbrel/umbrel-community-app-store` → **Use this template**.
2. Copy this whole folder into that repo as `agent-terminal/`
   (i.e. `agent-terminal/Dockerfile`, `agent-terminal/docker-compose.yml`, etc).
3. On your Umbrel: **App Store → ⋮ (top right) → Community App Stores →**
   paste your repo URL → **Add**.
4. Find "Agent Terminal" in the store and install it. Umbrel will build the
   image from the Dockerfile the first time — that takes a few minutes since
   it's installing Node, Herdr, Codex CLI, and Antigravity CLI.

## 2. Set a login credential (do this before exposing it anywhere)

Add an environment override so ttyd requires HTTP basic auth. In Umbrel,
set `APP_AGENT_TERMINAL_TTYD_CREDENTIAL=someuser:apassword` (or edit the
`environment:` block in `docker-compose.yml` directly). Without this,
**anyone who can load the app's URL gets a shell in the container.**

## 3. First-time setup once it's running

Open the app, and you'll land inside Herdr. From there, authenticate each
tool once (credentials persist in the `data/home` volume across restarts):

```
codex login       # or set OPENAI_API_KEY in the environment instead
agy               # Antigravity CLI — follow its login prompt on first run
```

Then start using them as Herdr panes, e.g. from inside Herdr:

```
codex
agy
```

Herdr's sidebar will track each pane's status (working / blocked / done).

## 4. Where your files live

- `/workspace` inside the container → `data/workspace` on disk. Put the
  repos you want these agents working on here so they survive rebuilds.
- `/root` inside the container → `data/home` on disk. This holds Herdr's
  config, Codex/Antigravity auth tokens, and SSH keys if you add any for
  git access.

## Notes / caveats

- This runs everything as root inside the container for simplicity —
  fine for a homelab box behind your own auth, not something to expose
  publicly as-is.
- If you use Tailscale or Umbrel's built-in remote access, prefer that
  over port-forwarding this app directly.
- ttyd sits behind Umbrel's reverse proxy fine, but if you ever see the
  terminal disconnect/hang, check that WebSocket upgrade headers and
  proxy timeouts aren't being stripped.
