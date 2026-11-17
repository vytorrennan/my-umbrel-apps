// Patches stremio-web's dependencies at image build time, after
// `pnpm install` and before `pnpm build`.
//
// 1. HLS gap jumping: stremio-video configures hls.js with maxBufferHole: 0,
//    so hls.js never jumps a gap in the buffer right away. Chrome reports a
//    gap of a frame or two before open-GOP keyframes (x265's default),
//    logging "This type of random access point is not well supported by MSE;
//    buffered range reporting may be less precise". Playback then stalls
//    about 5 s at each such keyframe until hls.js's stall recovery nudges
//    past it. With 0.5 s, hls.js jumps these 40 to 210 ms gaps almost at once.
//
// 2. ASS override tags in plain subtitles: many SRT subtitles (often from
//    OpenSubtitles, converted from fansub ASS files) contain tags such as
//    {\an8} (show this line at the top) or {\i1}. Desktop players hide them;
//    stremio-video showed them as text. The parser now removes every {\...}
//    tag, and lines tagged \an7, \an8 or \an9 are shown at the top of the
//    video instead of the bottom.
//
// Every patch must match exactly once, or the build fails, so a stremio-web
// update can't silently drop a change.
//
// Details: HLS-PASSTHROUGH.md, SUBTITLE-TAGS.md

const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const pnpmDir = path.join(root, "node_modules/.pnpm");
const pkgDirs = fs.readdirSync(pnpmDir)
    .filter((d) => d.startsWith("@stremio+stremio-video@"))
    .map((d) => path.join(pnpmDir, d, "node_modules/@stremio/stremio-video"))
    .filter((d) => fs.existsSync(d));

if (pkgDirs.length !== 1) {
    console.error(`patch-web: expected one stremio-video package, found ${pkgDirs.length}`);
    process.exit(1);
}
const pkg = pkgDirs[0];

const patches = [
    {
        file: "src/HTMLVideo/hlsConfig.js",
        before: "maxBufferHole: 0,",
        after: "maxBufferHole: 0.5,",
    },
    {
        // Strip {\...} tags from each cue and remember \an7-9 (top of screen).
        file: "src/withHTMLSubtitles/subtitlesParser.js",
        before: `            var cue = {
                startTime: (c.startTime * 1000) | 0,
                endTime: (c.endTime * 1000) | 0,
                text: c.text
            };`,
        after: `            var cueTags = c.text.match(/\\{\\\\[^}]*\\}/g) || [];
            var cue = {
                startTime: (c.startTime * 1000) | 0,
                endTime: (c.endTime * 1000) | 0,
                text: c.text.replace(/\\{\\\\[^}]*\\}/g, '').replace(/\\\\N/g, '\\n').trim(),
                top: cueTags.some(function(tag) { return /\\\\an[789](?![0-9])/.test(tag); })
            };`,
    },
    {
        file: "src/withHTMLSubtitles/subtitlesRenderer.js",
        before: `            var node = VTTJS.WebVTT.convertCueToDOMTree(window, cuesForTime[i].text);
            nodes.push(node);`,
        after: `            var node = VTTJS.WebVTT.convertCueToDOMTree(window, cuesForTime[i].text);
            node.subtitlesTop = cuesForTime[i].top === true;
            nodes.push(node);`,
    },
    {
        // Let the subtitles box span the video so cues can sit at the top.
        // pointer-events: none keeps clicks reaching the video underneath.
        file: "src/withHTMLSubtitles/withHTMLSubtitles.js",
        before: `        subtitlesElement.style.bottom = '0';
        subtitlesElement.style.left = '0';`,
        after: `        subtitlesElement.style.bottom = '0';
        subtitlesElement.style.top = '0';
        subtitlesElement.style.pointerEvents = 'none';
        subtitlesElement.style.left = '0';`,
    },
    {
        file: "src/withHTMLSubtitles/withHTMLSubtitles.js",
        before: `            subtitlesRenderer.render(cuesByTime, timeIndex).forEach(function(cueNode) {`,
        after: `            var topCuesElement = document.createElement('div');
            topCuesElement.style.position = 'absolute';
            topCuesElement.style.top = '3%';
            topCuesElement.style.right = '0';
            topCuesElement.style.left = '0';
            var bottomCuesElement = document.createElement('div');
            bottomCuesElement.style.position = 'absolute';
            bottomCuesElement.style.bottom = '0';
            bottomCuesElement.style.right = '0';
            bottomCuesElement.style.left = '0';
            subtitlesElement.appendChild(topCuesElement);
            subtitlesElement.appendChild(bottomCuesElement);
            subtitlesRenderer.render(cuesByTime, timeIndex).forEach(function(cueNode) {`,
    },
    {
        file: "src/withHTMLSubtitles/withHTMLSubtitles.js",
        before: `                subtitlesElement.appendChild(cueNode);
                subtitlesElement.appendChild(document.createElement('br'));`,
        after: `                var cuesElement = cueNode.subtitlesTop ? topCuesElement : bottomCuesElement;
                cuesElement.appendChild(cueNode);
                cuesElement.appendChild(document.createElement('br'));`,
    },
];

for (const { file, before, after } of patches) {
    const full = path.join(pkg, file);
    const src = fs.readFileSync(full, "utf8");
    const count = src.split(before).length - 1;
    if (count !== 1) {
        console.error(`patch-web: expected this once in ${file}, found it ${count} times:\n${before}`);
        process.exit(1);
    }
    fs.writeFileSync(full, src.replace(before, () => after));
    console.log(`patch-web: patched ${path.relative(root, full)}`);
}
