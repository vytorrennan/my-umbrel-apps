# Streaming server tracker client leak

Stremio's streaming server (`server.js`, v4.22.4 and possibly other versions)
leaks BitTorrent tracker clients. Once the app has been up for a few hours
with normal use, new torrents get no answers from trackers and buffer
forever. This image patches the leak at build time with
[`patch-server.js`](patch-server.js). It shipped in app version 1.0.3.

## Symptom

On 2026-11-14 the app had been running for about a day. Every new stream
then stayed on the loading screen. The server logs had nothing obvious:

```
-> GET /hlsv2/probe?mediaURL=...
Error: Probe process exited with code: 1
Engine created for 7eb5e279aa6968ff643bd370eec70479c51e7463
-> GET /7eb5e279.../0/stats.json   (repeats)
```

`stats.json` for the new torrents showed that no tracker had returned a
single peer, after 9 to 13 requests each:

```json
"peers": 0, "connectionTries": 0, "name": null,
"sources": [{"numFound": 0, "numRequests": 9,
             "url": "tracker:udp://tracker.opentrackr.org:1337/announce"}, ...]
```

The torrents themselves were healthy. Scraping the same trackers directly
from the same Umbrel showed 27 to 108 seeders for each one. A torrent that
had been open for hours (an episode already fully downloaded) showed where
the problem was:

```json
"connectionTries": 943071,
"sources": [{"numFound": 553100, "numFoundUniq": 81, "numRequests": 1844, ...}]
```

1844 requests to one tracker means about 15 hours of searching for peers.
553,100 peer addresses came back, but only 81 were distinct, and the swarm
had made 943,071 connection attempts to that same small set of peers. Even
that torrent's counters had stopped growing. Restarting the app fixed
playback at once: the same torrent found about 430 peers within 10 seconds.

## Cause

Peer search (`peerSearch`, around line 59486 of server.js) calls `run()` on
each source every 30 seconds while it is searching. For tracker sources,
`run()` is this wrapper around `bittorrent-tracker` (around line 60233):

```js
function Tracker(url, opts, infoHash) {
    ...
    this.run = function() {
        self.numRequests++;
        var client = new trackerCli(peerId, 6881, { infoHash: infoHash, announce: [ url ] });
        client.start(), client.on("peer", ...);
    }, this.pause = function() {};
}
```

The code has three problems:

- Every `run()` creates a new tracker client, and nothing ever destroys the
  old one.
- `client.start()` starts a re-announce timer in each client, set to the
  interval the tracker asks for (about 30 to 60 minutes). Each leaked client
  keeps announcing on its own timer for as long as the process runs.
- `pause()` does nothing, and the wrapper has no `close()`. When a torrent
  closes, peer search calls `x.close && x.close()` on each source, so its
  tracker clients keep running.

The result is one more permanent client per tracker every 30 seconds, for
every torrent opened since the server started. Stremio passes about 7 to 16
trackers per stream, so a few hours of watching leaves tens of thousands of
clients. They do two kinds of damage:

- The clients belonging to open torrents flood the swarm with duplicate peer
  addresses, which drives the endless connection attempts above.
- All of them send a constant stream of UDP announces: a new socket and a DNS
  lookup each time.

Eventually the server stops getting tracker answers at all, for old and new
torrents alike. Then any torrent without cached data finds no peers and
never starts.

We did not pin down exactly which resource runs out first. The leak itself
is certain and unbounded, and removing it removes the condition.

The **Ultra Fast** torrent profile (400 connections per torrent) makes the
peer churn worse, but it doesn't cause the leak. Any profile reaches the same
state given enough uptime.

## Fix

[`patch-server.js`](patch-server.js) runs in the Dockerfile right after the
checksum check of the downloaded server.js. It replaces the `Tracker`
wrapper with one that:

- creates a single client on the first `run()`;
- calls `client.update()` on later runs, which re-announces with the same
  client;
- adds `close()`, which destroys the client when the torrent closes;
- handles the client's `warning` and `error` events, so an unhandled
  `error` can't crash the process.

The search still announces every 30 seconds, exactly as upstream does. Only
the leak is gone.

The patch looks for the exact original code and fails the image build if it
doesn't find it exactly once. If a server update changes or fixes that code,
the build stops and the patch has to be reviewed, so the image can't ship
with the fix silently missing.

## Verification

Both servers ran locally, unmodified and patched, with a preload script that
counts live announce timers and UDP sockets. Each opened the same torrent
with 7 UDP trackers and was then told to close it (`GET /<infoHash>/remove`).

| | Original server.js | Patched server.js |
|---|---|---|
| Live tracker announce timers after 3 minutes | 49, growing by 7 every 30 s | 7, flat |
| After closing the torrent | 49, never freed | 0 |
| Trackers still return peers on each 30 s run | yes | yes |

The preload script (`probe.js`):

```js
const dgram = require('dgram'), fs = require('fs');
let live = new Set(), created = 0, udp = 0, udpLive = 0;
const si = global.setInterval, ci = global.clearInterval;
global.setInterval = function (fn, ms, ...a) {
    const t = si(fn, ms, ...a);
    if (ms >= 6e5) { created++; live.add(t); }   // tracker re-announce timers
    return t;
};
global.clearInterval = function (t) { live.delete(t); return ci(t); };
const cs = dgram.createSocket;
dgram.createSocket = function (...a) {
    const s = cs.apply(this, a); udp++; udpLive++;
    s.once('close', () => udpLive--);
    return s;
};
si(() => fs.appendFileSync(process.env.PROBE_OUT,
    `${new Date().toISOString().slice(11, 19)} announceTimersLive=${live.size} ` +
    `created=${created} udpCreated=${udp} udpOpen=${udpLive}\n`), 15000).unref();
```

To reproduce:

```sh
HOME=$PWD/home PROBE_OUT=$PWD/probe.log NO_CORS=1 node -r ./probe.js server.js &
H=7eb5e279aa6968ff643bd370eec70479c51e7463   # any healthy torrent
curl -s http://127.0.0.1:11470/$H/create -H 'content-type: application/json' \
  -d '{"peerSearch":{"sources":["tracker:udp://tracker.opentrackr.org:1337/announce",
       "tracker:udp://open.stealth.si:80/announce","dht:'$H'"],"min":40,"max":200}}'
# watch announceTimersLive in probe.log, then:
curl -s http://127.0.0.1:11470/$H/remove
```

Without the patch, `announceTimersLive` grows by one per tracker every 30
seconds and stays put after `/remove`. With the patch it equals the number of
trackers and drops to 0 after `/remove`.

## When updating the streaming server

1. Bump `STREMIO_SERVER_VERSION` and `STREMIO_SERVER_SHA256` in the
   Dockerfile and build.
2. If the build fails with `patch-server: expected the Tracker code once`,
   find the `function Tracker(url, opts, infoHash)` wrapper in the new
   server.js:
   - If upstream fixed the leak (one client per tracker, destroyed on
     close), delete the patch step from the Dockerfile.
   - Otherwise, update `before` and `after` in patch-server.js to match the
     new code.
3. Run the reproduction above against the new image's server.js to confirm
   that the timer count stays flat.
