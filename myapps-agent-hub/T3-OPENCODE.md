# T3 Code and the supervised OpenCode server

The existing dev-machine configuration makes T3 reuse Agent Hub's supervised
OpenCode server at `http://127.0.0.1:4096`. This avoids starting an additional
OpenCode server for model discovery. It is a local workaround for an intermittent
empty discovery result, not a fix to T3's upstream timeout or retry behavior.

## Persistence

T3 saves the provider instance in
`/home/developer/.t3/userdata/settings.json`, under
`providerInstances.opencode.config`. Its `serverUrl` selects the shared server
and its stored `serverPassword` supplies authentication. T3 may transform the
stored credential representation. Manage credentials through T3's provider
settings; do not copy the stored string into commands or release files.

Compose mounts the named `agent-hub-data` volume at `/home/developer`, so these
settings survive image updates, container restarts, and recreation when the same
volume is retained. The OpenCode server's existing password is also kept in
`/home/developer/.config/agent-hub/secrets.env`. Do not delete the home volume
when updating. Keep settings and secrets together when restoring a backup.

The image and entrypoint do not overwrite T3 provider settings or embed this
machine's credentials. A fresh home does not inherit this machine's workaround.
For a new installation, configure the OpenCode provider's server URL and its
existing server password in T3's provider settings. Use the password already
configured for the supervised OpenCode service. Do not paste credentials into
issues, logs, Git commits, or image layers.

## Verification after an update

Check `supervisorctl status t3 opencode`, then refresh OpenCode's status in T3's
provider settings and confirm that its model list is populated. The investigation
on 2026-10-19 observed 10 models. Model counts can change with account access.

Both services start automatically. A simultaneous cold boot can still produce a
transient discovery failure if OpenCode is not ready when T3 checks it. Refresh
the provider status after both services are running. Sharing the existing server
reduces cold-start work; it does not guarantee automatic recovery from every
startup race or server outage.

## Automatic shared-server updates

Agent Hub 1.0.15 and later run OpenCode through
`/usr/local/bin/agent-hub-opencode-server`. It watches the installed executable
and checks a changed CLI before restarting the server. An incomplete or failing
replacement leaves the existing server running. Reinstalling the same version
does not restart it. Supervisor still restarts a server that exits unexpectedly.

T3's PATH starts with `/usr/local/lib/agent-hub/provider-bin`. Its `npm` shim
forwards ordinary commands unchanged. After a successful global install of
`@opencode/cli`, it waits up to 25 seconds for the authenticated shared server to
report the installed version before returning success. This prevents T3's
immediate post-install check from reading the old server version. It reuses the
existing persisted Agent Hub password without printing or embedding it.

Updates can briefly interrupt OpenCode work when its server restarts. These
changes automate the reload; they do not change T3's upstream code. The image
bundles both helpers and generates their startup configuration on
every boot, so the automation survives recreation with this release and the
retained home volume.

The entrypoint also reuses `OPENCODE_JWT_SECRET` from its saved secrets file,
so the existing session-signing secret survives container recreation.
