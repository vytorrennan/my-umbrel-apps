#!/bin/bash
# ffmpeg wrapper for the Stremio streaming server (FFMPEG_BIN points here).
#
# The server's "vaapi-renderD128" profile decodes on the GPU
# (-hwaccel vaapi -hwaccel_output_format vaapi). Older Intel GPUs such as
# Ivy Bridge (HD 4000) encode H.264 but can't decode HEVC, so that profile
# fails on the server's own HEVC startup probe and is never offered.
#
# This rewrites those commands to decode on the CPU and upload frames to the
# GPU only for scaling and encoding, the expensive part. Every other command
# is passed through untouched. If the rewrite stops matching after a server
# update, the probe fails and the server falls back to CPU transcoding.
#
# Set STREMIO_VAAPI_HYBRID=0 to disable the rewrite.

REAL_FFMPEG=/usr/bin/ffmpeg

args=("$@")
n=${#args[@]}

rewrite=0
for ((i = 0; i < n - 1; i++)); do
    if [[ ${args[i]} == -hwaccel_output_format && ${args[i + 1]} == vaapi ]]; then
        rewrite=1
        break
    fi
done

if [[ $rewrite != 1 || ${STREMIO_VAAPI_HYBRID:-1} == 0 ]]; then
    exec "$REAL_FFMPEG" "$@"
fi

out=()
for ((i = 0; i < n; i++)); do
    arg=${args[i]}
    case $arg in
        -hwaccel | -hwaccel_output_format)
            # Drop GPU decoding; frames come out of the decoder in system memory.
            if [[ ${args[i + 1]} == vaapi ]]; then
                ((i++))
                continue
            fi
            ;;
        -vf | -filter:v)
            out+=("$arg")
            ((i++))
            chain=${args[i]}
            # Frames are already in system memory, nothing to download.
            chain=${chain#hwdownload,}
            if [[ $chain == *hwupload_vaapi* ]]; then
                # Subtitle burn-in: upload after the software filters.
                # (hwupload_vaapi only exists in jellyfin-ffmpeg.)
                chain=${chain//hwupload_vaapi/format=nv12,hwupload}
            elif [[ $chain != *hwupload* ]]; then
                chain="format=nv12,hwupload,$chain"
            fi
            out+=("$chain")
            continue
            ;;
    esac
    out+=("$arg")
done

exec "$REAL_FFMPEG" "${out[@]}"
