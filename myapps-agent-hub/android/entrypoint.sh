#!/usr/bin/env bash
set -euo pipefail

# ADB's emulator socket is local-only. Publish a separate forwarding socket on
# the isolated DinD network, with no Umbrel host port published.
socat TCP-LISTEN:5556,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:5555 &
socat TCP-LISTEN:5557,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:5554 &
socat TCP-LISTEN:8555,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:8554 &
"$ANDROID_HOME/platform-tools/adb" start-server >/dev/null
cameras=()
for facing in back front; do
  camera="$ANDROID_USER_HOME/../runtime/camera/$facing.png"
  if [ -f "$camera" ]; then
    cameras+=("-camera-$facing" "imagefile:$camera")
  else
    cameras+=("-camera-$facing" none)
  fi
done
exec "$ANDROID_HOME/emulator/emulator" -avd AgentHub_Pixel_Android_11 \
  -no-window -gpu swiftshader -feature -Vulkan -no-metrics -no-audio -no-boot-anim -no-snapshot \
  -memory 2048 -cores 2 -accel on -ports 5554,5555 -grpc 8554 -grpc-use-token \
  "${cameras[@]}"
