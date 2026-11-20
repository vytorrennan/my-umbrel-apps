// Patches the Stremio streaming server (server.js) at image build time.
//
// HLS segment bound: to play a file through HLS (needed for the audio
// language menu and embedded subtitles), the server tries to cut the video
// at its existing keyframes and pass it through unchanged. It gives up if a
// segment would be longer than 2x its 6 s target (12 s), and then decodes
// and re-encodes the whole video instead. Many x265/x264 releases use the
// encoder default of up to 250 frames between keyframes (about 10.4 s at
// 23.976 fps), which after merging short segments goes past 12 s. On a
// small Umbrel CPU that re-encode stutters, and it also forces 24 fps.
//
// Raising the bound to 3x (18 s) lets those files be passed through as-is.
// Longer segments only make seeking land up to a few seconds coarser.
//
// The build fails if the code to replace isn't found, so a server update
// can't silently drop the fix.
//
// Details: HLS-PASSTHROUGH.md

const fs = require("fs");

const file = process.argv[2];
let src = fs.readFileSync(file, "utf8");

const patches = [
    {
        name: "HLS video segment bound raised to 3x the target duration",
        before: "maxVideoSegmentDurationTs = 2 * segmentDurationTs",
        after: "maxVideoSegmentDurationTs = 3 * segmentDurationTs",
    },
    {
        // Passed-through video keeps ffmpeg's own decode times. The server
        // set each fragment's decode time (tfdt) to its earliest
        // presentation time. That is a no-op for most fragments but shifts
        // fragments that start with open-GOP leading pictures (frames
        // decoded after the keyframe but shown before it) by up to a few
        // hundred ms, leaving holes and overlaps in the timeline that make
        // the browser stall. Re-encoded video keeps the old behaviour.
        //
        // After a seek the server starts a new ffmpeg, and ffmpeg's decode
        // times then count from the seek point instead of from the start of
        // the file. hls.js still plays the video, but it takes that
        // difference as the stream's start time and shifts every embedded
        // subtitle cue by it, so after any seek or resume no subtitles show.
        // Each ffmpeg run therefore gets one fixed offset, taken from its
        // first fragment, that puts its decode times back on the file's
        // timeline (where the first segment starts at 0).
        name: "HLS passthrough video keeps ffmpeg's decode times on the file's timeline",
        before: `                        mp4.updateBaseMediaDecodeTime({
                            buffer: mediaSegmentBuffer,
                            baseMediaDecodeTime: sidx.earliestPresentationTime,
                            trackId: 1,
                            boxes: boxes
                        }), duration += `,
        after: `                        convertOptions.video && convertOptions.video.transcode ? mp4.updateBaseMediaDecodeTime({
                            buffer: mediaSegmentBuffer,
                            baseMediaDecodeTime: sidx.earliestPresentationTime,
                            trackId: 1,
                            boxes: boxes
                        }) : (() => {
                            const tfdt = boxes.find((({type: type}) => "moof" === type)).boxes.find((({type: type}) => "traf" === type)).boxes.find((({type: type}) => "tfdt" === type));
                            "number" != typeof targetConvertProcess.decodeTimeOffset && (targetConvertProcess.decodeTimeOffset = Math.round(targetMediaSegment.seekTime - mediaSegments.get(1).seekTime) - sidx.earliestPresentationTime);
                            mp4.updateBaseMediaDecodeTime({
                                buffer: mediaSegmentBuffer,
                                baseMediaDecodeTime: tfdt.baseMediaDecodeTime + targetConvertProcess.decodeTimeOffset,
                                trackId: 1,
                                boxes: boxes
                            });
                        })(), duration += `,
    },
];

for (const { name, before, after } of patches) {
    const count = src.split(before).length - 1;
    if (count !== 1) {
        console.error(`patch-server: expected "${before}" once in ${file}, found it ${count} times`);
        process.exit(1);
    }
    src = src.replace(before, after);
    console.log(`patch-server: ${name}`);
}

fs.writeFileSync(file, src);
