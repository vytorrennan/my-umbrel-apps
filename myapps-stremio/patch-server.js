// Patches the Stremio streaming server (server.js) at image build time.
//
// Tracker leak: the server's peer search calls Tracker.run() every 30 seconds
// for each tracker of every open torrent. Upstream, run() builds a brand-new
// bittorrent-tracker client each time and never destroys it (pause() is a
// no-op and there is no close()). Every client keeps re-announcing on its
// own timer for as long as the process lives, even after its torrent is
// closed. Over a day of watching, tens of thousands of clients pile up,
// flooding the swarm with duplicate peers and the process with tracker
// traffic, until new torrents get no tracker answers at all and buffer
// forever. A restart clears it.
//
// The fix keeps one client per tracker: later runs re-announce with
// client.update(), and close() destroys the client when the torrent closes.
//
// The build fails if the code to replace isn't found, so a server update
// can't silently drop the fix.
//
// Full write-up and reproduction steps: TRACKER-LEAK.md

const fs = require("fs");

const file = process.argv[2];
let src = fs.readFileSync(file, "utf8");

const before = `    function Tracker(url, opts, infoHash) {
        var self = this;
        EventEmitter.call(this);
        var peerId = new Buffer("01234567890123456789");
        this.run = function() {
            self.numRequests++;
            var client = new trackerCli(peerId, 6881, {
                infoHash: infoHash,
                announce: [ url ]
            });
            client.start(), client.on("peer", (function(addr) {
                self.emit("peer", addr);
            }));
        }, this.pause = function() {};
    }`;

const after = `    function Tracker(url, opts, infoHash) {
        var self = this, client = null;
        EventEmitter.call(this);
        var peerId = new Buffer("01234567890123456789");
        this.run = function() {
            self.numRequests++;
            if (client) return void client.update();
            client = new trackerCli(peerId, 6881, {
                infoHash: infoHash,
                announce: [ url ]
            });
            client.on("peer", (function(addr) {
                self.emit("peer", addr);
            })), client.on("warning", (function() {})), client.on("error", (function() {})), client.start();
        }, this.pause = function() {}, this.close = function() {
            client && (client.destroy(), client = null);
        };
    }`;

const count = src.split(before).length - 1;
if (count !== 1) {
    console.error(`patch-server: expected the Tracker code once in ${file}, found it ${count} times`);
    process.exit(1);
}
src = src.replace(before, after);
fs.writeFileSync(file, src);
console.log("patch-server: tracker client leak fixed");
