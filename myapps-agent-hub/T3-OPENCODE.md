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
