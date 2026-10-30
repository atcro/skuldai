# Skuld demo video: recorded storyboard (2:29, hard limit under 3:00)

Status: **RECORDED 2026-10-30** from `scripts/video/` against the dashboard served from
commit `f46da06` over `evidence/` (gate records frozen at `1d11d51`, see
`evidence/G12/frozen_commit.txt`). Output: `evidence/video/skuld_demo.mp4`,
1280x720, 30 fps, 149.4 s.

## What is real and what is generated

- **Voice:** AI-generated, Kokoro TTS (`kokoro-js` 1.2.1, voice `af_heart`, speed 1.05),
  run locally. The intro card says so, and a standing line under the picture repeats it
  for the whole video.
- **Dashboard footage:** real-time screen recordings of the Skuld dashboard
  (`uvicorn skuld.api.main:app`) in Google Chrome, driven by `puppeteer-core` over the
  Chrome DevTools screencast. Scrolling, page loads and the embedded video playback are
  the live page. Zoom 1.15-1.3 is browser zoom on the page. No speed changes.
- **Simulator clips:** the archived MuJoCo renders under `evidence/` listed per row,
  scaled 640x480 -> 920x690 with no change in time. Last frame held where narration
  runs longer than the clip.
- **Evidence JSON on screen:** the files served by the dashboard's `/evidence/` mount,
  shown in Chrome's plain JSON view.
- **Generated graphics:** two static title cards (intro, outro) and two static side
  panels next to the simulator clips. Their numbers are copied from the files named on
  each panel. No animation.
- **Numbers spoken:** every one is in the "Facts" table below with its source file.

## Timeline

| Time | Screen | Source | Narration |
|---|---|---|---|
| 0:00-0:09 | intro card with transparency statement | `cards/intro.png` | "This is an AI narration over real screen recordings of Skuld running. Nothing on screen is mocked, animated, or sped up." |
| 0:09-0:22 | nominal push (clip) + panel | `evidence/G05/nominal.mp4` | "In MuJoCo, a Franka Panda pushes a block into a target region. This classical controller passes its nominal test three times, bit for bit identical. Would you ship it?" |
| 0:22-0:41 | Test Lab `/`: cards, comparison curves, full active-search ledger | screen recording | "Skuld perturbs four physical variables: block offset, mass, friction and observation delay. Same budget of twenty-five episodes: random testing found three failures, the first at episode sixteen. Active search found six, the first at episode six, and closer to nominal." |
| 0:41-0:58 | first random failure (clip) + panel | `evidence/G07/first_random_failure.mp4`, `evidence/G07/random/rand-015.result.json` | "The first failure random search found: delay one hundred fifty-two milliseconds, mass and friction raised. A deterministic oracle reads simulator state and applies the rule never collision. The finger touched the floor at three and a half seconds. No model decides this." |
| 0:58-1:18 | Counterexample Replay `/counterexample`: cards, original vs minimized table, minimized episode playing in the page | screen recording | "The minimizer reverts offset, mass and friction one at a time; the failure survives each revert. One variable remains: one hundred forty milliseconds of observation delay. Three replays, byte identical, stored as a regression test." |
| 1:18-1:30 | `/evidence/G08/tavily_search.json` (request id), then `/evidence/G08/constraints/approved/panda-payload-kg.json` (approval_state, authorizer, approved_at) | screen recording | "A live Tavily search pulled the manufacturer's three kilogram payload figure. It became a constraint only after a human approved it; name and timestamp are in the record." |
| 1:30-1:50 | `/evidence/G04/attempt1_rejected/generate_call.json` (validation: quote not verbatim), `/evidence/G04/generate_call.json` (model id, validation accepted), `/evidence/G04/scenario.result.json` (SAFETY_FAIL) | screen recording | "Nemotron, an NVIDIA model on Nebius Token Factory, proposed the constraint and a hypothesis. Its first quote was not verbatim, so the validator refused it and kept the rejection. The accepted hypothesis ran in simulation: finger on the floor. The model proposes; physics decides." |
| 1:50-2:10 | Release Gate `/release`: v1 BLOCKED + reasons, v2 ELIGIBLE, repair video playing in the page, fault-injection table | screen recording | "The release gate blocks version one on its stored counterexample and on two held-out cases it never searched. A repaired version two is eligible: it passed the named simulation suite, which never means safe. Nine injected faults, from missing telemetry to corrupt artifacts, all fail closed." |
| 2:10-2:23 | Failure Atlas `/atlas`, then `/evidence/G12/g12_report.json` at the v2 nearest-failure block | screen recording | "Same budget, same oracle: active search found closer failures than random. The next round broke version two again at one hundred eighty-two milliseconds. That is the next regression test." |
| 2:23-2:29 | outro card | `cards/outro.png` | "Skuld. What your robot policy owes before it ships." |

Visibly operating modules (dashboard recordings plus simulator clips): about 125 s of
149 s, against the 60 s rule minimum.

## Facts the narration uses (all EXECUTED, with source)

| Spoken | Value | Source |
|---|---|---|
| nominal passes three times, bit-identical | 3/3 PASS, `bit_identical: true` | `evidence/G07/nominal_runs.csv`, `evidence/G12/g12_report.json` |
| four variables | offset, mass, friction, observation delay | `evidence/G07/protocol.json` domain |
| budget 25; random 3 failures, first at 16 | 3/25, episode 16, nearest 0.885 | `evidence/G07/metrics.json` |
| active 6 failures, first at 6, closer | 6/25, episode 6, nearest 0.781 | `evidence/G10/comparison.json` |
| rand-015: 152 ms delay, mass and friction raised, floor contact at 3.5 s | 152.38 ms, 0.282 kg, 0.729, t=3.520 s step 175, NEVER collision | `evidence/G07/random_baseline.csv`, `evidence/G07/random/rand-015.result.json` |
| minimized: 140 ms delay, others nominal, 3 replays identical | `kept_variables: [observation_delay_ms]`, 140.04 ms, 3/3 | `evidence/G10/counterexample.json`, `evidence/G10/g10_report.json` |
| Tavily, 3 kg, human approval with name and time | request id `8910bea1-...`, value 3.0 kg, authorizer Adam Crozier, approved_at 2026-10-27T03:40:27Z | `evidence/G08/tavily_search.json`, `evidence/G08/constraints/approved/panda-payload-kg.json` |
| Nemotron first quote rejected, second accepted, scenario SAFETY_FAIL | `nvidia/Nemotron-3_5-Lightning`; "quote does not occur verbatim in the cited snippet"; status SAFETY_FAIL | `evidence/G04/attempt1_rejected/generate_call.json`, `evidence/G04/generate_call.json`, `evidence/G04/scenario.result.json` |
| v1 BLOCKED on regression + 2 held-out; v2 ELIGIBLE; 9 faults fail closed | heldout-001, heldout-004 SAFETY_FAIL; `fault_injection_all_fail_closed: true` | `evidence/G11/g11_report.json` |
| next round broke v2 at 182 ms | v2 active nearest 1.013, scenario at 182 ms delay | `evidence/G12/g12_report.json` |

## Words not used

certified, safe (except "never means safe"), proven, global minimum, causal, learned
(for this controller), GR00T. Nemotron is named only for the G04 step, as "proposed".

## How to re-record

See `scripts/video/README.md`. Order: `tts.mjs` (voice + `plan.json`), `cards.mjs`,
`capture.mjs` (needs the dashboard on 127.0.0.1:8765), `assemble.mjs`.
