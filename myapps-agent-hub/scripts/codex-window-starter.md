# Codex window starter

Agent Hub starts `codex-window-starter` through supervisord on every boot. The entrypoint installs the bundled Python script into `/home/developer/.local/share/codex-window-starter` and writes its supervisor program directly into the generated configuration.

The home volume preserves `state.json`, ChatGPT authentication, and service logs across container recreation. The entrypoint refreshes the script without replacing the saved state. Compose mounts the entrypoint and Python source from this app directory so the existing image receives these changes on recreation; the Dockerfile also bundles both for future image builds.

The script permits only `gpt-6-luna` with `low` reasoning. It sends an ephemeral `OK` message every five hours and one minute, subject to available allowance. It preserves its deadline instead of chasing the moving reset timestamp reported for idle windows. It never redeems reset credits.

Check: `supervisorctl status codex-window-starter`

Logs: `/home/developer/.local/share/codex-window-starter/service.log`

Stop until the next startup: `supervisorctl stop codex-window-starter`

Validation: `python3 scripts/test_codex_window_starter.py`, `bash -n entrypoint.sh`, and `docker compose config --quiet`.
