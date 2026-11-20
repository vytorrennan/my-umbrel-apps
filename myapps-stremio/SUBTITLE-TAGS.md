# Subtitle override tags

Many plain-text subtitles, often from OpenSubtitles, were converted from
fansub ASS files and still contain ASS override tags:

```
{\an8}SHINJUKU POLICE STATION
{\i1}Where are you going?{\i0}
```

`{\an8}` means "show this line at the top centre". Desktop players such as
VLC and mpv understand it and hide the tags. Stremio's web player showed them
as text, at the bottom of the screen:

- The streaming server's `/subtitles.vtt` endpoint, which converts add-on
  subtitles to WebVTT, copies each line's text as is (it only escapes `&`).
- stremio-video's SRT converter removes HTML tags like `<i>`, but nothing
  removes `{\...}` tags. This is true in 0.0.103 (stremio-web v5.1.0) and
  0.0.105.

Embedded ASS tracks are not affected; they go through the ASS renderer.

## Fix (app 1.0.9, updated in 1.0.10)

`patch-web.js` changes stremio-video before the web UI is built. Since 1.0.10
the parser code is the same as the upstream PR
[Stremio/stremio-video#212](https://github.com/Stremio/stremio-video/pull/212),
including the changes a Stremio maintainer asked for in review.

- `subtitlesParser.js`, for each cue:
  - lines tagged `\an7`, `\an8` or `\an9` are marked as top cues;
  - `\i` and `\b` become `<i>` and `<b>`, kept nested because vtt.js only
    closes the innermost tag; `\b` weights below 700 are not bold;
  - other `{\...}` tags are removed; a tag must close on its own line;
  - `\N` and `\n` become a line break and `\h` a space;
  - cues with nothing left after removing tags (like a lone
    `{\fad(200,200)}`) are skipped.
- `subtitlesRenderer.js`: passes the top mark on to the cue's DOM node.
- `withHTMLSubtitles.js`: the subtitles box now covers the whole video
  (`pointer-events: none`, so clicks still reach the video). Top cues go in
  a box 3% from the top. All other cues go in a box at the bottom, which
  still follows the "Vertical Position" setting.

Text in braces that doesn't start with a backslash, like `{laughs}`, is
left alone.

Each patch must match exactly once, or the build fails.

## Checking it

Bundle the patched stremio-video (`src/HTMLVideo` wrapped with
`src/withHTMLSubtitles`), play a short clip in Chromium, add a VTT track
with a `{\an8}` line, an italic-tagged line and a plain line, and observe
the `time`, `paused` and `buffering` props (the player only tracks time
when something observes it). The `{\an8}` line should show at the top
without the tag, and the other two at the bottom.

## Overlapping built-in subtitles (app 1.0.12)

Built-in subtitle tracks in HLS mode are drawn by the browser. stremio-video
placed every cue by percentage (`snapToLines = false`,
`line = 100 - offset`) to apply the "Vertical Position" setting. When
several cues show at once, such as a sign and a line of dialogue, Chrome 157
draws such cues on top of each other. Chrome 158 stacks them.

`patch-web.js` now places built-in cues by line (`snapToLines = true`). The
browser stacks those itself. The vertical position becomes a number of
lines from the bottom, worked out from the subtitle font size and the video
height, and is redone when the window is resized.

Checked in the real web app in Chrome 157 with a test file holding the
8:02 scene of *Dead Mount Death Play* (three poster signs and a dialogue
line at once), vertical position 20%: before, the dialogue was drawn over
the "Starring" sign; after, all lines are stacked and readable.
