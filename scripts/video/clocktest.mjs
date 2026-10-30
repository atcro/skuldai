import puppeteer from "puppeteer-core";
import { startRecording } from "./rec.mjs";
const fps = Number(process.argv[2] || 25);
const browser = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true,
  defaultViewport: { width: 1280, height: 690, deviceScaleFactor: 1 } });
const page = await browser.newPage();
await page.setContent(`<body style="background:#111;color:#fff;font:bold 120px monospace"><div id=c></div><div id=s style="height:3000px"></div><script>
const t0=performance.now();(function f(){document.getElementById('c').textContent=((performance.now()-t0)/1000).toFixed(2);requestAnimationFrame(f)})();</script></body>`);
await new Promise(r => setTimeout(r, 500));
const rec = await startRecording(page, "clockrec");
const w0 = Date.now();
await new Promise(r => setTimeout(r, 4000));
await page.evaluate(() => window.scrollTo({ top: 300, behavior: "smooth" }));   // some motion
await new Promise(r => setTimeout(r, 6000));
const r = await rec.stop("clockrec.mp4"); console.log(r);
console.log("fps", fps, "wall", (Date.now() - w0) / 1000);
await browser.close();
