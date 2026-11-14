# Streaming server tracker client leak

Stremio's streaming server (`server.js`) up to v4.22.4 leaks BitTorrent
tracker clients. Once the app has been up for a few hours with normal use,
new torrents get no answers from trackers and buffer forever.

**Status: fixed upstream in streaming server v4.22.5**, which this app uses
from version 1.0.4. App version 1.0.3 shipped a local patch for it
(`patch-server.js`, now removed). The rest of this page records the
investigation and how to check that the bug stays fixed.

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

The leaking code isn't in a Stremio repository. It comes from the small
`peer-search` library that the server bundles,
[Ivshti/peer-search](https://github.com/Ivshti/peer-search). It was fixed
there in PR #5, "Fix tracker lookups and tracker client leak", merged on
2026-10-24. That fix shipped in streaming server v4.22.5, published on
2026-10-27. The fixed `Tracker` wrapper:

- creates a single client per tracker and calls `client.update()` on later
  runs;
- adds `close()`, which destroys the client when the torrent closes;
- resolves UDP tracker hostnames itself, caching each answer for 10 minutes,
  and skips IPv6 peers.

Search the bundled server.js for `function Tracker(url, opts, infoHash)` to
check which version a build has. The fixed one has a `this.close = function`
and calls `client.update()`.

App version 1.0.3, built on v4.22.4, made the same change with a build-time
patch, `patch-server.js`. App version 1.0.4 moved to v4.22.5 and dropped the
patch.

## Verification

v4.22.4 (unmodified and with the 1.0.3 patch) and v4.22.5 ran locally with a preload script that
counts live announce timers and UDP sockets. Each opened the same torrent
with 7 UDP trackers and was then told to close it (`GET /<infoHash>/remove`).

| | v4.22.4 | v4.22.4 + patch | v4.22.5 |
|---|---|---|---|
| Live tracker announce timers after 3 minutes | 49, growing by 7 every 30 s | 7, flat | 7, flat |
| After closing the torrent | 49, never freed | 0 | 0 |
| Trackers still return peers on each 30 s run | yes | yes | yes |

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

After bumping `STREMIO_SERVER_VERSION` and `STREMIO_SERVER_SHA256` in the
Dockerfile, run the reproduction above against the new server.js.
`announceTimersLive` should equal the number of trackers and drop to 0 after
`/remove`. If it keeps growing, the leak is back.
