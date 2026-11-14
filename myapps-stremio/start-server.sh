#!/bin/bash
# Logs whether the GPU is usable for VAAPI encoding, then starts the
# streaming server. The server's own hardware probe gives no reason when it
# fails, so this line is the place to look when "Transcode profile" only
# offers "Disabled".

gpu_check() {
    local dev=/dev/dri/renderD128
    echo "gpu-check: running as $(id)"
    if [[ ! -e /dev/dri ]]; then
        echo "gpu-check: /dev/dri is not present in the container (no GPU passed through); transcoding will use the CPU"
        return
    fi
    echo "gpu-check: /dev/dri contents (numeric owner/group):"
    ls -ln /dev/dri | sed 's/^/gpu-check:   /'
    if [[ ! -r $dev || ! -w $dev ]]; then
        echo "gpu-check: $dev is not readable and writable by this user; add its group id to group_add"
        return
    fi
    local out
    if out=$(/usr/bin/ffmpeg -hide_banner -loglevel error -init_hw_device "vaapi=va:$dev" -filter_hw_device va \
        -f lavfi -i testsrc2=size=640x360:rate=24 -t 0.5 -vf format=nv12,hwupload -c:v h264_vaapi -f null - 2>&1); then
        echo "gpu-check: OK, VAAPI H.264 encoding works on $dev"
    else
        echo "gpu-check: VAAPI H.264 encoding FAILED on $dev:"
        echo "$out" | tail -n 5 | sed 's/^/gpu-check:   /'
    fi
}

gpu_check
exec node /opt/stremio-server/server.js
