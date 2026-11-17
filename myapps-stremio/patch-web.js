// Patches stremio-web's dependencies at image build time, after
// `pnpm install` and before `pnpm build`.
//
// HLS gap jumping: stremio-video configures hls.js with maxBufferHole: 0,
// so hls.js never jumps a gap in the buffer right away. Chrome reports a gap
// of a frame or two before open-GOP keyframes (x265's default), logging
// "This type of random access point is not well supported by MSE; buffered
// range reporting may be less precise". Playback then stalls about 5 s at
// each such keyframe until hls.js's stall recovery nudges past it. With
// 0.5 s, hls.js jumps these 40 to 210 ms gaps almost at once.
//
// The build fails if the code to replace isn't found, so a stremio-web
// update can't silently drop the change.
//
// Details: HLS-PASSTHROUGH.md

const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const pnpmDir = path.join(root, "node_modules/.pnpm");
const files = fs.readdirSync(pnpmDir)
    .filter((d) => d.startsWith("@stremio+stremio-video@"))
    .map((d) => path.join(pnpmDir, d, "node_modules/@stremio/stremio-video/src/HTMLVideo/hlsConfig.js"))
    .filter((f) => fs.existsSync(f));

if (files.length !== 1) {
    console.error(`patch-web: expected one stremio-video hlsConfig.js, found ${files.length}`);
    process.exit(1);
}

const file = files[0];
const before = "maxBufferHole: 0,";
const after = "maxBufferHole: 0.5,";
let src = fs.readFileSync(file, "utf8");
const count = src.split(before).length - 1;
if (count !== 1) {
    console.error(`patch-web: expected "${before}" once in ${file}, found it ${count} times`);
    process.exit(1);
}
fs.writeFileSync(file, src.replace(before, after));
console.log(`patch-web: hls.js maxBufferHole set to 0.5 in ${path.relative(root, file)}`);
