// Static title cards and side panels (1280x690 PNG) rendered from HTML in Chrome. Values are copied from
// the evidence files named on each card; no figure here is typed from memory.
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
fs.mkdirSync("cards", { recursive: true });

const css = `
  * { box-sizing: border-box; }
  body { margin: 0; width: 1280px; height: 690px; background: #0f1216; color: #e6e8eb;
         font-family: "Segoe UI", system-ui, sans-serif; overflow: hidden; }
  .full { padding: 70px 90px; height: 690px; display: flex; flex-direction: column; justify-content: center; }
  h1 { font-size: 64px; margin: 0; letter-spacing: .5px; }
  h1 small { font-size: 26px; color: #9aa3ad; font-weight: 400; margin-left: 18px; }
  .sub { font-size: 26px; color: #c9d1d9; margin: 14px 0 0; }
  .meta { font-size: 19px; color: #9aa3ad; margin: 10px 0 0; }
  .box { margin-top: 44px; border: 1px solid #2a303a; background: #171b21; border-radius: 8px; padding: 20px 24px;
         font-size: 20px; line-height: 1.45; color: #c9d1d9; max-width: 1040px; }
  .box b { color: #58a6ff; }
  .panel { position: absolute; left: 920px; top: 0; width: 360px; height: 690px; background: #171b21;
           border-left: 1px solid #2a303a; padding: 26px 24px; display: flex; flex-direction: column; gap: 10px; }
  .k { font-size: 12px; color: #9aa3ad; text-transform: uppercase; letter-spacing: .8px; }
  .t { font-size: 24px; font-weight: 600; line-height: 1.2; }
  .n { font-size: 14px; color: #9aa3ad; line-height: 1.35; }
  table { border-collapse: collapse; width: 100%; font-size: 15px; margin-top: 4px; }
  td { padding: 5px 0; border-bottom: 1px solid #2a303a; }
  td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
  .badge { display: inline-block; padding: 4px 14px; border-radius: 12px; font-size: 18px; font-weight: 600; border: 1px solid; }
  .PASS { color: #3fb950; border-color: #3fb950; } .SAFETY_FAIL { color: #f85149; border-color: #f85149; }
  .mono { font-family: Consolas, ui-monospace, monospace; font-size: 13px; color: #9aa3ad; word-break: break-all; }
  .grow { flex: 1; }
`;

const cards = {
  intro: `<div class="full">
    <h1>Skuld <small>falsification-driven CI/CD for embodied robot policies</small></h1>
    <p class="sub">Finds the smallest world change that breaks a robot policy, minimizes it, stores it as a replayable regression test, and blocks releases that fail it.</p>
    <p class="meta">Team ODIN &nbsp;·&nbsp; Nebius × NVIDIA Global AI Hackathon, Physical AI track &nbsp;·&nbsp; Apache-2.0</p>
    <div class="box"><b>Transparency.</b> The voice is AI-generated (Kokoro TTS). Everything on screen is real: screen recordings of the Skuld dashboard running in Chrome over archived run records, and simulator clips that are the stored MuJoCo renders of those episodes. No mock screens, no animation, no speed-ups.</div>
  </div>`,
  outro: `<div class="full">
    <h1>Skuld</h1>
    <p class="sub">What your robot policy owes before it ships.</p>
    <p class="meta">github.com/atcro/skuldai &nbsp;·&nbsp; Apache-2.0 &nbsp;·&nbsp; Team ODIN</p>
    <div class="box">Results describe the tested simulation envelope: CPU MuJoCo, one Franka Panda push task, one classical controller, four perturbation variables. Not a real robot, not a safety certification.<br><br>AI narration over real recordings. Every number spoken is read from a file under <b>evidence/</b> in the public repository.</div>
  </div>`,
  s1: `<div class="panel">
    <div class="k">Archived simulator render</div>
    <div class="t">Nominal episode</div>
    <div class="n">Franka Panda pushes the block into the target region. Policy <b>push-dls-ik-v1</b>: classical damped-least-squares IK, no learning.</div>
    <table>
      <tr><td>object offset</td><td>0.000 m</td></tr>
      <tr><td>object mass</td><td>0.100 kg</td></tr>
      <tr><td>friction</td><td>0.600</td></tr>
      <tr><td>observation delay</td><td>0.0 ms</td></tr>
    </table>
    <div><span class="badge PASS">PASS</span></div>
    <div class="n">G07 protocol: 3 nominal runs, 3 / 3 PASS, bit-identical trajectories.</div>
    <div class="grow"></div>
    <div class="mono">evidence/G05/nominal.mp4<br>evidence/G07/nominal_runs.csv</div>
  </div>`,
  s3: `<div class="panel">
    <div class="k">Archived simulator render</div>
    <div class="t">First random failure</div>
    <div class="n">Scenario <b>rand-015</b>, episode 16 of 25 in the random baseline. Same policy, same scene.</div>
    <table>
      <tr><td>object offset</td><td>−0.022 m</td></tr>
      <tr><td>object mass</td><td>0.282 kg</td></tr>
      <tr><td>friction</td><td>0.729</td></tr>
      <tr><td>observation delay</td><td>152.4 ms</td></tr>
    </table>
    <div><span class="badge SAFETY_FAIL">SAFETY_FAIL</span></div>
    <div class="n">Oracle rule <b>NEVER collision</b>: left finger in contact with the floor at t = 3.52 s (step 175). Distance from nominal 0.885.</div>
    <div class="grow"></div>
    <div class="mono">evidence/G07/first_random_failure.mp4<br>evidence/G07/random/rand-015.result.json</div>
  </div>`,
};

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true,
  defaultViewport: { width: 1280, height: 690, deviceScaleFactor: 1 } });
const page = await browser.newPage();
for (const [name, body] of Object.entries(cards)) {
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body}</body></html>`);
  await page.screenshot({ path: `cards/${name}.png` });
  console.log("card", name);
}
await browser.close();
