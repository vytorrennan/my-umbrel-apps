# Agent Hub

Agent Hub runs T3 Code, OpenCode, OpenChamber, and a browser terminal on Umbrel. The developer home volume stores shell configuration and tool installations; projects are mounted at `/home/developer/Projects`.

## T3 terminal completion

The image includes `bash-completion` and loads it in interactive Bash terminals. Commands complete after `sudo`, including `sudo t3-` followed by Tab. The entrypoint also enables completion in existing `.bashrc` files on the persistent home volume.

Open a new T3 terminal after applying the change, or reload the current Bash configuration:

```bash
source ~/.bashrc
```

## T3 nightly updates

Run the updater from a T3 terminal:

```bash
t3-nightly-autoupdate
```

It compares the installed and running versions with the latest nightly. If the package is already current but the server is older, it still restarts the server. Supervisor stops the whole T3 process group so the previous server cannot retain port 3773.

The restart and verification run in a detached session and continue when the T3 terminal disconnects. After reconnecting, check the result:

```bash
tail -n 10 /var/log/agent-hub/t3-autoupdate.log
```

A successful restart logs `verified running server: <version>`. Restart failures are logged as errors. If the main log is not writable, the updater uses `/tmp/t3-autoupdate.log`.

## Keypad Home in the desktop app

Keypad 7 with Num Lock off requires a client-side fix in affected T3 desktop builds. The [T3 Code customizations](https://github.com/vytorrennan/t3code-customizations) launcher supplies that fix. Container shell settings alone cannot correct a key the desktop client does not transmit.

## Release 1.0.10

Release 1.0.10 includes Bash completion after `sudo`, process-group cleanup during T3 restarts, and detached nightly restarts that verify the active server version. It also bundles Docker Buildx alongside the Docker CLI, so `docker buildx build` is available without installing an extra package. The separate desktop keypad fix is supplied by the customization launcher linked above.

## Applying source changes

The Dockerfile and entrypoint include these changes for future image builds. Pushing this repository does not rebuild or publish the image referenced by `docker-compose.yml`; build and deploy an updated image to apply them to a newly created container. The live container was patched separately and both terminal fixes were verified on 2026-10-11.

From this directory, build the versioned image and `latest` using the bundled Buildx plugin:

```bash
docker buildx build --platform linux/amd64 --load \
  -t vytor/agent-hub:1.0.10 -t vytor/agent-hub:latest .
```

Docker in Agent Hub connects to its DinD sidecar. Building or publishing an image there does not replace the running Umbrel container; apply the release through Umbrel separately.
