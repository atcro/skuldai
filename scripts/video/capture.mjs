// Real-time screen recordings of the Skuld dashboard in Google Chrome (puppeteer screencast).
// Reads plan.json (segment durations from tts.mjs); writes cap/<id>.webm. Usage: node capture.mjs [id ...]
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import { startRecording } from "./rec.mjs";

const BASE = process.env.SKULD_URL || "http://127.0.0.1:8765";
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const plan = JSON.parse(fs.readFileSync("plan.json", "utf8"));
const only = new Set(process.argv.slice(2));
fs.mkdirSync("cap", { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  defaultViewport: { width: 1280, height: 690, deviceScaleFactor: 1 },
  args: ["--autoplay-policy=no-user-gesture-required", "--no-first-run", "--mute-audio"],
});
const page = await browser.newPage();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const take = { rec: null, id: null, t0: 0 };
async function open(path, zoom) {
  await page.goto(BASE + path, { waitUntil: "networkidle0" });
  await page.evaluate((z) => { document.body.style.zoom = String(z); window.scrollTo(0, 0); }, zoom);
  await sleep(300);
  if (!take.rec) {   // first page of a segment: start the recording on a settled page and start the clock
    take.rec = await startRecording(page, `cap/${take.id}`);   // timestamped frames -> cap/<id>.mp4, real time by construction
    take.t0 = Date.now();
  }
}
// Wait for all <video> metadata so the page does not reflow mid-recording.
async function videosReady() {
  await page.evaluate(() => Promise.all([...document.querySelectorAll("video")].map((v) =>
    v.readyState >= 1 ? null : new Promise((r) => { v.addEventListener("loadedmetadata", r, { once: true }); setTimeout(r, 3000); }))));
}
// Eased scroll to an absolute document y over ms (requestAnimationFrame driven, real time).
async function glide(toY, ms) {
  await page.evaluate((toY, ms) => new Promise((res) => {
    const y0 = window.scrollY, t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo(0, y0 + (toY - y0) * e);
      if (k < 1) requestAnimationFrame(step); else res();
    };
    requestAnimationFrame(step);
  }), toY, ms);
}
const docY = (sel, nth = 0, block = "start") => page.evaluate((sel, nth, block) => {
  const el = document.querySelectorAll(sel)[nth];
  if (!el) throw new Error("no element " + sel + " #" + nth);
  const r = el.getBoundingClientRect();
  const top = window.scrollY + r.top;   // Chrome 128+: rects are already in zoomed CSS px
  if (block === "center") return top - (window.innerHeight - r.height) / 2;
  return top - 12;
}, sel, nth, block);
async function toSel(sel, nth = 0, block = "start", ms = 900) { await glide(await docY(sel, nth, block), ms); }
async function toBottom(ms) { await glide(await page.evaluate(() => document.body.scrollHeight * parseFloat(document.body.style.zoom || "1") - window.innerHeight), ms); }
// Scroll so that the first occurrence of `needle` in the page text sits near the given fraction of the viewport.
async function toText(needle, frac = 0.3, ms = 900) {
  const y = await page.evaluate((n, frac) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const i = node.textContent.indexOf(n);
      if (i < 0) continue;
      const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + n.length);
      return window.scrollY + r.getBoundingClientRect().top - window.innerHeight * frac;
    }
    throw new Error("text not found: " + n);
  }, needle, frac);
  await glide(Math.max(0, y), ms);
}
async function play(nth = 0) {
  await page.evaluate((nth) => { const v = document.querySelectorAll("video")[nth]; v.muted = true; return v.play(); }, nth);
}

// Each choreography receives `at(sec)` which waits until that second of the segment.
const shots = {
  s2: async (at) => {                       // Test Lab: cards, curves, then the full candidate ledger
    await open("/", 1.2); await videosReady();
    await at(5); await toSel("h2", 0, "start"); await at(9.5);
    await toBottom(await at.remaining() - 600);
  },
  s4: async (at) => {                       // Counterexample Replay: cards, table, play the minimized episode
    await open("/counterexample", 1.2); await videosReady();
    await at(4); await toSel("h2", 0, "start"); await at(9);
    await toSel("video", 1, "center"); await play(1);
  },
  s5: async (at, dur) => {                  // Tavily record, then the human-approved constraint
    await open("/evidence/G08/tavily_search.json", 1.3);
    await at(1); await toText('"request_id"', 0.15);
    await at(dur * 0.45); await open("/evidence/G08/constraints/approved/panda-payload-kg.json", 1.3);
    await at(dur * 0.45 + 0.8); await toText('"approval_state"', 0.55);
  },
  s6: async (at, dur) => {                  // Nemotron: rejected attempt, accepted call, executed scenario verdict
    await open("/evidence/G04/attempt1_rejected/generate_call.json", 1.3);
    await at(0.6); await toText('"validation"', 0.1);
    await at(dur * 0.4); await open("/evidence/G04/generate_call.json", 1.3);
    await at(dur * 0.4 + 2.5); await toText('"validation"', 0.1);
    await at(dur * 0.72); await open("/evidence/G04/scenario.result.json", 1.3);
  },
  s7: async (at) => {                       // Release Gate: v1 BLOCKED + reasons, v2 ELIGIBLE, repair video, fault table
    await open("/release", 1.15); await videosReady();
    await at(3); await toSel("ul.reasons", 0, "center");
    await at(6.5); await toSel(".status-big", 1, "start");
    await at(9); await toSel("video", 0, "center"); await play(0);
    await at(14); await toSel("h2", 3, "start", 1200);
  },
  s8: async (at, dur) => {                  // Failure Atlas, then the G12 rerun record (v2 nearest failure)
    await open("/atlas", 1.2);
    await at(dur * 0.5); await open("/evidence/G12/g12_report.json", 1.3);
    await at(dur * 0.5 + 0.6); await toText("181.56639277801307", 0.5);   // the v2 nearest failure scenario (182 ms delay)
  },
};

for (const seg of plan.segments) {
  if (seg.kind !== "screen" || (only.size && !only.has(seg.id))) continue;
  const dur = seg.dur;
  take.rec = null; take.id = seg.id; take.t0 = Date.now();
  const at = async (sec) => { const rem = take.t0 + sec * 1000 - Date.now(); if (rem > 0) await sleep(rem); };
  at.remaining = async () => take.t0 + dur * 1000 - Date.now();
  await shots[seg.id](at, dur);
  await at(dur);
  const r = await take.rec.stop(`cap/${seg.id}.mp4`);
  console.log(seg.id, "recorded", r.seconds.toFixed(2), "s,", r.frames, "frames (planned", dur, "s)");
}
await browser.close();
