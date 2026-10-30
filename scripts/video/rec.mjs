// Real-time page recorder on the raw DevTools screencast. Every frame Chrome emits is kept with its own
// capture timestamp; the video is then sampled from those timestamps on a constant frame grid, so playback
// time equals wall time by construction. Puppeteer's page.screencast() was measured
// at 6-20 % off real time on this machine (frame-count rounding against a fixed container rate).
import fs from "node:fs";
import { spawnSync } from "node:child_process";

export async function startRecording(page, dir, { quality = 95, fps = 30 } = {}) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const client = await page.createCDPSession();
  const frames = [];   // {file, t}  t = seconds since epoch, from Chrome's own frame metadata
  client.on("Page.screencastFrame", (e) => {
    const file = `f${String(frames.length).padStart(5, "0")}.jpg`;
    fs.writeFileSync(`${dir}/${file}`, Buffer.from(e.data, "base64"));
    frames.push({ file, t: e.metadata.timestamp });
    client.send("Page.screencastFrameAck", { sessionId: e.sessionId }).catch(() => {});
  });
  await client.send("Page.startScreencast", { format: "jpeg", quality, maxWidth: 1280, maxHeight: 690, everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  return {
    async stop(outMp4) {
      const tEnd = Date.now() / 1000;
      await client.send("Page.stopScreencast").catch(() => {});
      await client.detach().catch(() => {});
      if (!frames.length) throw new Error("no frames captured in " + dir);
      // Sample the captured frames on a constant 30 fps grid: output frame k (time start + k/fps) shows the
      // latest frame Chrome had emitted by then. Hard links, so no pixel is copied or altered.
      const start = Math.min(t0, frames[0].t);
      const n = Math.round((tEnd - start) * fps);
      let j = 0;
      for (let k = 0; k < n; k++) {
        const t = start + k / fps;
        while (j + 1 < frames.length && frames[j + 1].t <= t) j++;
        const out = `${dir}/o${String(k).padStart(5, "0")}.jpg`;
        try { fs.linkSync(`${dir}/${frames[j].file}`, out); } catch { fs.copyFileSync(`${dir}/${frames[j].file}`, out); }
      }
      const r = spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-framerate", String(fps),
        "-i", `${dir}/o%05d.jpg`, "-vf", "scale=1280:690:flags=bicubic,format=yuv420p",
        "-c:v", "libx264", "-crf", "16", "-preset", "fast", outMp4], { stdio: "inherit" });
      if (r.status !== 0) throw new Error("ffmpeg failed for " + dir);
      return { frames: frames.length, seconds: tEnd - start };
    },
  };
}
