# Audio language menu and HLS passthrough

Five fixes that work together so files with several audio tracks get an audio
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

## 3. Passthrough video had holes in its timeline (app 1.0.7)

With passthrough working, *Dead Mount Death Play* S01E02 still got stuck
partway through. The episode was fully downloaded and the server answered
every segment request in under a second; the player had simply stopped.

The server runs ffmpeg with `-c:v copy -movflags frag_keyframe+...`, so
each keyframe starts an fMP4 fragment, and it then rewrites every
fragment's decode time (`tfdt`) to the fragment's earliest presentation
time from its `sidx`:

```js
mp4.updateBaseMediaDecodeTime({ ..., baseMediaDecodeTime: sidx.earliestPresentationTime, ... })
```

For most fragments that changes nothing: ffmpeg's `tfdt` already equals
the earliest presentation time, to within 16 ticks of a 1/16000 timescale.
But x265 uses open GOPs by default, so some keyframes are followed by
leading pictures, frames decoded after the keyframe but shown before it.
In those fragments the earliest presentation time is earlier, and the
rewrite moves the whole fragment later by up to a few hundred ms. That
leaves a hole before the fragment and an overlap after it.

Concatenating every video segment of S01E02 from the unpatched server
(34,046 frames, none actually missing) showed:

| | v4.22.5 | v4.22.5 + patch |
|---|---|---|
| Holes over 60 ms | 9 (40 to 210 ms) | 0 |
| Duplicate timestamps | 5 | 0 |
| Decode times going backwards | 6 | 0 |
| Same, for a session started at segment 100 (a seek) | 5 / 2 / 3 | 0 / 0 / 0 |

The holes sit exactly at keyframes with leading pictures (450.37 s with 5,
516.98 s with 2, and so on). The browser's buffer then has gaps and
overlapping frames, and Stremio's hls.js config (`maxBufferHole: 0`) won't
jump gaps, so playback can stall for good.

Fix: `patch-server.js` skips the rewrite for passed-through video and keeps
ffmpeg's decode times, which are continuous by construction. Re-encoded
video still gets the rewrite. After a seek, the timestamps are the same as
before (ffmpeg's first `tfdt` 118784 vs the rewritten 118800), so audio
sync and seeking behave as they did.

To check a file, concatenate the init segment and every video segment of a
session and look at the packet timestamps:

```sh
ffprobe -v error -show_entries packet=pts_time,dts_time -of csv=p=0 cat.mp4
```

There should be no pts jumps larger than one frame and no dts going
backwards.

Reported upstream as
[Stremio/stremio-bugs#2941](https://github.com/Stremio/stremio-bugs/issues/2941).

## 4. Chrome stalled briefly at open-GOP keyframes (app 1.0.8)

On 1.0.7, S01E02 played to the end, but Helium's `chrome://media-internals`
log showed two stalls of about 5 seconds. Each was a `DEMUXER_UNDERFLOW` on
video, followed by an hls.js seek just past it (to 519.89 s and 618.71 s).
They came right after the keyframes at 516.98 s and 615.66 s, which have
leading pictures. Chrome logged:

```
Warning: presentation time of most recently processed random access point
(517.058 s) is later than the presentation time of a non-keyframe (517.017 s)
that depends on it. This type of random access point is not well supported
by MSE; buffered range reporting may be less precise.
```

Chrome's MSE reports a gap of a frame or two before such keyframes even when
the data is there. stremio-video sets hls.js `maxBufferHole: 0`, so hls.js
only gets past the gap through its slower stall recovery.

Fix: `patch-web.js` sets `maxBufferHole: 0.5` in stremio-video's
`hlsConfig.js` before the web UI is built. hls.js then jumps gaps up to
0.5 s as soon as it detects the stall. These gaps are 40 to 210 ms, so
nothing visible is skipped. The build fails if the line isn't found.

Confirmed on 1.0.8: S01E02 played from 479 s for about 7 minutes, past both
keyframes, with no `DEMUXER_UNDERFLOW` or recovery seek in media-internals.

Check a build with:

```sh
docker run --rm vytor/stremio:<tag> sh -c 'grep -o "maxBufferHole:[^,]*" -r /srv/stremio-web --include=main.js'
```

It should print `maxBufferHole:.5` (the `.1` next to it is hls.js's own
default and isn't used).

## 5. Embedded subtitles vanished after a seek (app 1.0.11)

Embedded subtitle tracks showed nothing when playback started partway
through an episode (a resume, a seek, or a reload), in every language and
with any torrent. This also happens with the unpatched v4.22.5 server.

After a seek the server starts a new ffmpeg at that point. ffmpeg's video
decode times (`tfdt`) then count from the seek point, not from the start of
the file, and so did the server's old rewrite to the `sidx` earliest
presentation time. hls.js still plays the video: it sees the jump and takes
the difference as the stream's start time (`initPTS`). But the server's
WebVTT segments use the file's own times and have no `X-TIMESTAMP-MAP`, so
hls.js shifts every cue by `-initPTS`. Started at 50 s, a test file got
`initPTS` -40 s, and the cue for 0:38 was scheduled at 1:18.

Fix: `patch-server.js` gives each ffmpeg run one fixed offset, taken from
its first fragment: the segment's start time on the file's timeline minus
that fragment's earliest presentation time. Every fragment of that run gets
ffmpeg's decode time plus this offset. A run started at the beginning gets
an offset of 0, so nothing changes there. Decode times stay continuous
within a run, so fix 3 still holds.

Checked with the bundled hls.js (1.5.4-patch2) in Chromium, with a VP9 test
file whose subtitle cues are labelled with their own times:

| | v4.22.5 | 1.0.11 |
|---|---|---|
| Start at 50 s | `initPTS` -40 s, cue for 0:38 at 1:18, nothing shown | `initPTS` 0, cue for 0:58 shown at 0:58 |
| Start at 0, seek to 70 s (server restarts ffmpeg) | | `initPTS` 0, cue for 1:10 shown at 1:10 |

On an open-GOP x265 test file, a run started at segment 5 begins at
40.04 s, the segment's start, with no holes over 60 ms and no decode times
going backwards. It lines up with a run started at 0 to within one frame.

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

`patch-server.js` fails the build if any code it changes is gone. If that
happens, look for `Video segment duration cannot be bounded` in the new
server.js, find the new bound, and rerun the test above.

`patch-web.js` fails the build if stremio-video's `maxBufferHole: 0` line
is gone after a stremio-web update. Check whether the new stremio-video
still needs the change before updating the patch.
