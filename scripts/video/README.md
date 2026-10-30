# Demo video pipeline

Builds `evidence/video/skuld_demo.mp4` from real recordings only. Runs on the Windows
side (Chrome + Node + ffmpeg) against the dashboard served from WSL2.

What is generated and what is recorded is listed in `docs/video_script.md`.

## Requirements

- Google Chrome at `C:/Program Files/Google/Chrome/Application/chrome.exe` (or `CHROME=`)
- Node 22+ and ffmpeg on PATH
- the dashboard: `wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/dashboard_serve.sh`
- `npm install` in this folder (`puppeteer-core`, `kokoro-js`; the Kokoro model, about
  90 MB, downloads from Hugging Face on first run). Both are local; no API key, no cost.

## Steps, in order

```
cd scripts/video
npm install
node tts.mjs        # narration.json -> audio/*.wav + plan.json (segment durations)
node cards.mjs      # static intro/outro cards and the two clip side panels -> cards/*.png
node capture.mjs    # real-time Chrome screen recordings of the dashboard -> cap/*.webm
node assemble.mjs   # cut, concatenate, draw the transparency line -> skuld_demo.mp4
```

`node capture.mjs s7` re-records one segment; `node assemble.mjs s7` rebuilds one segment
without the final concat.

## Honesty notes

- `capture.mjs` does not use puppeteer's `page.screencast()`: measured against an on-screen
  clock it played 6-20 % off real time (frame-count rounding against a fixed container
  rate). `rec.mjs` instead keeps every frame Chrome emits with Chrome's own capture
  timestamp and samples them onto a constant 30 fps grid, so video time equals wall time
  by construction (`clocktest.mjs` verifies this: constant offset, under 30 ms drift).
  Nothing in `assemble.mjs` changes playback speed (`setpts` only resets timestamps after
  `trim`).
- Segment length is set by the narration; when a simulator clip is shorter than its
  narration the last frame is held (`tpad=stop_mode=clone`), never looped or slowed.
- Numbers on the side panels are typed from the files named on the panel. Change the
  evidence and they must be re-checked by hand.
