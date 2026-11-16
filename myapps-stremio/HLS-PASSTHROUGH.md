# Audio language menu and HLS passthrough

Two fixes that work together so files with several audio tracks get an audio
language menu and still play smoothly on the Umbrel's CPU.

## How the player picks a playback mode

Before playing, the web player (`@stremio/stremio-video`,
`withStreamingServer.js`) asks the server to probe the file
(`/hlsv2/probe?mediaURL=...`). Then:

- If the browser can play every stream and the file has one audio track and
  no embedded subtitles, it plays the raw file directly.
- Otherwise it plays it through the server's HLS mode
  (`/hlsv2/<id>/master.m3u8`). HLS lists each audio track and embedded
  subtitle track, so the player can offer a menu for them.
- If the probe fails, it falls back to playing the raw file directly. The
  browser then plays only the default audio track and there is no menu.

## 1. The server couldn't probe its own streams (app 1.0.5)

The player builds `mediaURL` from the browser's origin, for example
`https://server.<tailnet>.ts.net:11471/<infoHash>/<idx>`. The server
container can't reach that public address, so every probe failed with
`Probe process exited with code: 1`, and every multi-audio file played
without an audio menu.

Fix: the Caddyfile rewrites `mediaURL` and `videoUrl` query values that point
at the same host the request came in on to `http://127.0.0.1:11470/`. Other
URLs (debrid links, other hosts) are left alone.

Check: from a client, the probe through the public address returns streams:

```sh
curl -s "https://<host>:11471/hlsv2/probe?mediaURL=https%3A%2F%2F<host>%3A11471%2F<infoHash>%2F0"
```

## 2. HLS re-encoded video with far-apart keyframes (app 1.0.6)

In HLS mode the server tries to cut the video at its keyframes and pass it
through unchanged (`segmenter.retrieve`). It refuses if any segment would be
longer than `maxVideoSegmentDurationTs = 2 * segmentDurationTs` (12 s for the
6 s target), and then decodes and re-encodes the whole video to H.264.

Many x265/x264 releases keep the encoder default of up to 250 frames between
keyframes, about 10.4 s at 23.976 fps. The segmenter merges short segments
into the next one, so merged segments pass 12 s. With `HLS_DEBUG=1` the
server logs:

```
init:transcoding:Video segment duration cannot be bounded
```

On the Umbrel (Ivy Bridge, 4 threads, a GPU that can't decode HEVC) this
meant software-decoding 10-bit 1080p HEVC and re-encoding it, which
stuttered. The re-encode also forces 24 fps, so a 23.976 fps source gets a
duplicated frame about every 5 seconds.

Fix: `patch-server.js` raises the bound to `3 * segmentDurationTs` (18 s).
The build fails if that line isn't found exactly once.

Tested with *Dead Mount Death Play* S01E01 (EMBER, HEVC Main 10, two AAC
tracks, keyframe gaps up to 10.43 s):

| | v4.22.5 | v4.22.5 + patch |
|---|---|---|
| Video in HLS | re-encoded to H.264, 24 fps | original HEVC Main 10, 23.976 fps |
| Segment lengths | 4 s | 4 to 10.4 s |
| Decodes cleanly from segment 1 and from segment 50 | yes | yes |

## Reproducing

Run the image with a local copy of a file and debug logging. Bind mounts
didn't work with this Docker setup, so files are copied in. `fs.js` is a
small Node static file server with range support listening on port 9000.

```sh
docker create --name sdbg -e HLS_DEBUG=1 -e HLS_DEBUG_DIR=/tmp/p vytor/stremio:<tag> \
  bash -c 'mkdir -p /tmp/p; node /tmp/fs.js /tmp/ep.mkv & exec node /opt/stremio-server/server.js'
docker cp fs.js sdbg:/tmp/fs.js; docker cp ep.mkv sdbg:/tmp/ep.mkv; docker start sdbg
docker exec sdbg bash -c '
  Q="mediaURL=http%3A%2F%2F127.0.0.1%3A9000%2Fep.mkv&videoCodecs=h264&videoCodecs=hevc&audioCodecs=aac&maxAudioChannels=2"
  curl -s -o /dev/null "http://127.0.0.1:11470/hlsv2/t/master.m3u8?$Q"
  curl -s -o /tmp/i.mp4 "http://127.0.0.1:11470/hlsv2/t/video0/init.mp4?$Q"
  ffprobe -v error -show_entries stream=codec_name -of compact /tmp/i.mp4
  grep -h "init:" /tmp/p/media_video*'
```

`codec_name=hevc` means passthrough. `codec_name=h264` plus
`cannot be bounded` in the log means the bound is still too tight.

## When updating the streaming server

`patch-server.js` fails the build if the line it changes is gone. If that
happens, look for `Video segment duration cannot be bounded` in the new
server.js, find the new bound, and rerun the test above.
