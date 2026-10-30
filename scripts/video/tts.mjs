// Kokoro TTS for every narration line; writes audio/<id>.wav and plan.json (segment durations).
import { KokoroTTS } from "kokoro-js";
import fs from "node:fs";

const segs = JSON.parse(fs.readFileSync("narration.json", "utf8"));
fs.mkdirSync("audio", { recursive: true });
const SPEED = Number(process.env.SPEED || 1.05);
const VOICE = process.env.VOICE || "af_heart";
const tts = await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", { dtype: "q8", device: "cpu" });
let total = 0;
for (const s of segs) {
  const a = await tts.generate(s.text, { voice: VOICE, speed: SPEED });
  await a.save(`audio/${s.id}.wav`);
  s.audio_s = a.audio.length / a.sampling_rate;
  s.dur = Math.max(s.min_s, Math.ceil((s.audio_s + 0.6) * 10) / 10);
  total += s.dur;
  console.log(s.id, "audio", s.audio_s.toFixed(1), "s  segment", s.dur, "s");
}
fs.writeFileSync("plan.json", JSON.stringify({ voice: VOICE, speed: SPEED, total, segments: segs }, null, 1));
console.log("total", total.toFixed(1), "s");
