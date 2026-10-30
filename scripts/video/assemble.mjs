// Cuts every segment to its planned duration at 1280x720 / 30 fps with its narration, concatenates them,
// and draws the standing transparency line in the 30 px band under the picture. No speed changes anywhere.
import fs from "node:fs";
import { spawnSync } from "node:child_process";

const REPO = process.env.SKULD_REPO || "C:/Skuld";
const OUT = process.env.OUT || "skuld_demo.mp4";
const plan = JSON.parse(fs.readFileSync("plan.json", "utf8"));
fs.mkdirSync("seg", { recursive: true });
const only = new Set(process.argv.slice(2));   // build only these segment ids and skip the final concat

function ff(args) {
  const r = spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("ffmpeg failed: " + args.join(" "));
}
const enc = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"];
// Narration starts 0.4 s into each segment and the segment is padded with silence to its planned length.
const aud = (i, d) => `[${i}:a]adelay=400:all=1,aresample=48000,apad,atrim=duration=${d}[a]`;

for (const s of plan.segments) {
  if (only.size && !only.has(s.id)) continue;
  const d = s.dur, out = `seg/${s.id}.mp4`, wav = `audio/${s.id}.wav`;
  if (s.kind === "card") {
    ff(["-loop", "1", "-framerate", "30", "-i", `cards/${s.card}.png`, "-i", wav,
        "-filter_complex", `[0:v]pad=1280:720:0:0:color=0x0f1216,trim=duration=${d},format=yuv420p[v];${aud(1, d)}`,
        "-map", "[v]", "-map", "[a]", "-t", String(d), ...enc, out]);
  } else if (s.kind === "clip") {
    // Archived 640x480 render scaled 1.4375x (no interpolation in time), last frame held if narration runs longer.
    ff(["-i", `${REPO}/${s.clip}`, "-loop", "1", "-framerate", "30", "-i", `cards/${s.card}.png`, "-i", wav,
        "-filter_complex",
        `[0:v]fps=30,scale=920:690:flags=lanczos,tpad=stop_mode=clone:stop_duration=60[c];` +
        `[1:v][c]overlay=0:0,pad=1280:720:0:0:color=0x0f1216,trim=duration=${d},setpts=PTS-STARTPTS,format=yuv420p[v];${aud(2, d)}`,
        "-map", "[v]", "-map", "[a]", "-t", String(d), ...enc, out]);
  } else {
    ff(["-i", `cap/${s.id}.mp4`, "-i", wav,
        "-filter_complex",
        `[0:v]fps=30,scale=1280:690,tpad=stop_mode=clone:stop_duration=60,pad=1280:720:0:0:color=0x0f1216,trim=duration=${d},setpts=PTS-STARTPTS,format=yuv420p[v];${aud(1, d)}`,
        "-map", "[v]", "-map", "[a]", "-t", String(d), ...enc, out]);
  }
  console.log("segment", s.id, d, "s");
}

if (only.size) process.exit(0);
fs.writeFileSync("list.txt", plan.segments.map((s) => `file 'seg/${s.id}.mp4'`).join("\n") + "\n");
fs.writeFileSync("bar.txt", "AI narration (Kokoro TTS)  ·  real screen recordings of Skuld in Chrome  ·  simulator clips are archived MuJoCo renders  ·  no speed-ups  ·  tested simulation envelope only");
ff(["-f", "concat", "-safe", "0", "-i", "list.txt",
    "-filter_complex", "[0:v]drawtext=fontfile='C\\:/Windows/Fonts/segoeui.ttf':textfile=bar.txt:fontsize=15:fontcolor=0x9aa3ad:x=(w-text_w)/2:y=698[v]",
    "-map", "[v]", "-map", "0:a", ...enc, "-movflags", "+faststart", OUT]);
console.log("wrote", OUT);
