# Android device for T3 Code

Agent Hub can run an optional headless Android phone through its existing DinD
daemon. Android Studio and a desktop environment are not needed. The DinD sidecar
is already privileged and exposes the host's KVM device to nested containers;
the main Agent Hub container does not need KVM passthrough or recreation.

Run `agent-hub-android setup` once as developer. It downloads checksum-verified
Android command-line tools 20.0, accepts the SDK licenses, installs the emulator,
platform tools and Android 11 AOSP x86_64 system image, creates the virtual
phone, builds the small local runtime image, and starts it. Java and emulator
discovery libraries are provided by the Agent Hub image. Setup requires internet
access and several GB of disk space. Repeating setup stops the emulator before
updating SDK packages, then recreates its container while retaining phone data.
The AOSP image omits Google apps and Play Services to reduce load on this host.
Apps that require those services need a different image and more resource
headroom. When changing the system-image flavor, setup preserves the previous
AVD under `~/Projects/.agent-hub/android/backups` instead of overwriting its data.

## Storage and startup

- SDK and emulator state are under `~/Projects/.agent-hub/android`. This Projects
  path is already mounted at the same absolute location in the DinD sidecar.
- `~/Android/Sdk` and the SDK commands in `~/.local/bin` point to that SDK.
- `~/Library/Android/sdk` is a compatibility symlink for device-hub 0.15.3,
  which otherwise defaults to that macOS-style path even on Linux when an
  existing T3 process has no `ANDROID_HOME`. Future startup sets it explicitly.
- The main `~/.android` holds its normal ADB state. The emulator has separate
  state under `~/Projects/.agent-hub/android/user`, including its AVD and protected
  ADB keys. Keeping these AVDs separate prevents T3 offering to boot the same
  phone again inside the main container, where KVM is absent.
- DinD retains the local image `agent-hub/android-emulator:1` and the container
  `agent-hub-android` in its existing data volume. Its restart policy is
  `no`, so explicit shutdown and DinD restarts leave it stopped. The SDK and guest data are bind-mounted from Projects.
- Supervisor's `android-adb` forwards console/ADB sockets to localhost and
  registers the phone as `emulator-5554` while
  `~/.config/agent-hub/android-enabled` exists. Fresh installations do not download
  Android or start an emulator automatically.

The phone uses KVM, software graphics, 2 GiB guest RAM, two virtual CPUs and a
480-by-800 screen. Emulator 37.2.12 raised the initial 1 GiB request to a 2 GiB
minimum, so the configuration now states that effective allocation explicitly.
Its container has a 3072 MiB memory limit, 4096 MiB combined
memory/swap limit and three-CPU quota. It runs as developer's UID/GID with the KVM
device group added. The extra CPU quota lets rendering run alongside the two
guest CPUs. No physical GPU, display server or USB access is required.
The 8 GiB Umbrel host also runs other services and VMs. First boot can be slow
and this emulator can add swap pressure; this is not a promise of smooth operation
under simultaneous builds or VM workloads.

ADB and console listen locally inside the emulator container and are forwarded
through container ports 5556/5557 to DinD ports 5555/5554. The main container's
bridge binds only to 127.0.0.1 on those ports and registers the normal emulator
transport with the local ADB server. A mode-600 console token is shared through
a file mount and matching regular `~/.emulator_console_auth_token`, so `adb emu avd name`
can authenticate. T3 requires that console lookup when discovering emulators.
ADB refuses a symlink for this credential file.
The Umbrel Compose file does not publish these ports on the host. Use
`agent-hub-android stop` to stop it, and `agent-hub-android start` to
bring it back. `agent-hub-android status` shows container and ADB state. The phone
is named `AgentHub_Pixel_Android_11`, matching T3's supported Pixel profiles.
The SDK facade now lets T3 list and boot the stopped managed phone.
Stop/setup flush Android's guest filesystem before stopping QEMU. Raw Docker
stop can discard recent writes still held in the guest's page cache.
Use the helper to power the phone off. The runtime restart policy is `no`, so explicit shutdown stays off. Closing
the stream leaves the phone running; no idle shutdown is implemented.

For apps served on dev-machine, use ADB reverse, for example
`adb -s emulator-5554 reverse tcp:8081 tcp:8081` for Metro. The guest's
`10.0.2.2` points to the emulator container, which is a different network host.
ADB reverse was verified with a temporary HTTP server on dev-machine.

## T3 setup and verification

In Settings, Integrations, Devices, select this environment and enable Device
hub and Agent device access. Refresh Android support and open the running phone
from the thread's Devices panel. T3 installs its own device tools as needed.
Agent access changes apply to new agent sessions; an existing session can retain
a credential that denies device MCP tools even when the saved setting is enabled.

Check `adb -s emulator-5554 shell getprop sys.boot_completed`, which must return `1`,
then verify discovery, live streaming and input in T3. ADB connectivity and an
Android screenshot alone do not establish that T3's streaming/control works.
Keep credentials and the phone's data out of Git and the published image.

## Video dependencies and container bridge

T3 requires FFmpeg with libx264 on the main container PATH. The main Dockerfile
installs Ubuntu ffmpeg. Verify with an actual libx264 encode, not only an encoder
listing. Device hub 0.15.3 defaults to gRPC screenshot capture. The emulator uses
`-grpc 8554 -grpc-use-token`; its localhost endpoint is forwarded through the
isolated DinD network and the main loopback bridge. The helper publishes
mode-600 discovery metadata under `~/.android/avd/running` with its own live
bridge PID and the runtime bearer token. These files are credentials and must
never enter Git or images. No gRPC port is published by Umbrel Compose.
After a runtime replacement, reconnect the T3 device panel to replace stale
stream state. FFmpeg and these source changes await the next Agent Hub release.

## Android video frame rate

The managed bridge applies 24 FPS to the existing local device hub through its
stream-settings API when Android is enabled. It discovers the current hub port
from T3 state and changes only h264Fps when necessary. Missing/idle hubs are
ignored. This does not implement idle shutdown and does not start video streams.
No T3 package is patched. Future API/state-path changes may require adaptation.
The first live setting was applied directly without restarting the existing
bridge; its updated code becomes active on the next bridge start.

## Start the phone from T3

The SDK presented at `~/Android/Sdk` is a facade. Its emulator executable points
to `/usr/local/bin/agent-hub-emulator`, and its avdmanager points to
`/usr/local/bin/agent-hub-avdmanager`. Both come from
`scripts/agent-hub-emulator.py`. The real SDK remains intact at
`~/Projects/.agent-hub/android/sdk`; the DinD phone uses that real path.
`~/Library/Android/sdk` points to the facade for already-running T3 processes.

The avdmanager adapter lists the real persistent AVD with its proper path and
boot marker. The emulator adapter supports list/version/help/acceleration probes,
T3's `-avd` launch and `@name` form, port selection, software GPU options, and
T3's camera placeholder image files. Image files are copied into the shared
runtime directory and refreshed by the bridge. Host webcams are unsupported.
Only `AgentHub_Pixel_Android_11` is managed; arbitrary AVD creation/deletion,
wipe-data, native GPU rendering and unrecognized launch flags fail explicitly.
SDK updates still operate on the real SDK; rerun `install-facade` after adding
new SDK top-level components. No installed T3 package is modified.

The launcher serializes starts with a file lock, refuses conflicting duplicate
port requests, starts the DinD runtime, and stays alive via `docker wait` for
T3's process tracking. Main-loopback console/ADB ports follow T3's selected even
port from 5554 through 5682, forwarding to fixed isolated DinD ports. The selected
port is saved under `console-port`; use that serial for manual ADB operations.

During cold boot, a PID-owned `launch-starting` marker gates main ADB publication
until the guest reports `sys.boot_completed=1`. This prevents T3 attempting video
before Android is ready. The wrapper allows 160 seconds for guest boot, within
T3's current 180-second ADB wait, apart from runtime image preparation. Slow
host workloads can still exceed that deadline. Failures are recorded in
`~/Projects/.agent-hub/android/launcher.log`; no SDK download happens on launch.

The runtime has restart policy `no`. Explicit T3 power-off remains off; closing
the panel leaves Android running. There is no idle shutdown. The console bridge
flushes guest storage before forwarding `kill`, including fragmented console
requests, and refuses the shutdown if the flush fails. The CLI helper retains
its own sync-before-stop path. Startup installs the facade when an SDK exists,
and the helper rebuilds the small runtime image when its bundled source digest
changes, recreating only a stopped outdated runtime. Existing AVD data is kept.
The setup/launch scripts and source are pending an Agent Hub image release.

## Off-state resource use

The bridge subscribes to DinD start/stop events and blocks when Android is off.
It releases its forwarding ports and discovery metadata, and runs no ADB/video
checks or camera copying until the runtime starts. This works independently of
the enabled marker, which is configuration rather than proof of a running phone.
It reconnects after a DinD outage and handles a missing/recreated runtime. T3's
own shared device helpers remain under T3's lifecycle; no idle shutdown is added.
