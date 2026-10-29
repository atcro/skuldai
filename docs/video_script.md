# Skuld demo video script (target 2:50, hard limit under 3:00)

Every clip below is an archived run artifact. Every number is read from a file
under `evidence/`. Screen recordings are of the dashboard served by
`uvicorn skuld.api.main:app --port 8765` over the same evidence. No speed-ups.
Mock screens: none.

| Time | Screen | Source file | Narration (one line, ~12 words) |
|---|---|---|---|
| 0:00-0:12 | nominal push, robot succeeds | `evidence/G05/nominal.mp4` (7 s) + Test Lab header | "This push controller passes its nominal test, three times, bit-identical. Would you ship it?" |
| 0:12-0:35 | Test Lab: ledger filling, 25/25, 6 failures | screen recording of `/` | "Skuld perturbs four physical variables only: offset, mass, friction, observation delay. Random testing found 3 failures in 25; active search found 6, the first at episode 6." |
| 0:35-0:58 | the first random failure, finger on floor; oracle verdict | `evidence/G07/first_random_failure.mp4`, then `evidence/G07/random/rand-015.result.json` on screen | "It breaks under a small concrete change. The verdict comes from a deterministic oracle reading simulator state: NEVER collision, finger on the floor." |
| 0:58-1:25 | Counterexample Replay: original vs minimized table, then minimized video | screen recording of `/counterexample`, `evidence/G10/minimized_failure.mp4` | "The minimizer reverts offset, mass and friction. The failure survives. One variable remains: 140 ms of observation delay. Three replays, byte-identical." |
| 1:25-1:43 | Tavily evidence -> approved constraint (human) | `evidence/G08/tavily_search.json`, `constraints/approved/panda-payload-kg.json` (authorizer and timestamp visible) | "Evidence from the manufacturer's datasheet becomes a constraint only after a human approves it." |
| 1:43-2:00 | Nemotron step: attempt 1 rejected, attempt 2 accepted, hypothesis, oracle verdict | `evidence/G04/attempt1_rejected/generate_call.json` validation block (reason: quote not verbatim), then `evidence/G04/generate_call.json` (model id, accepted), `hypothesis_nemotron.json`, `scenario.result.json`. On-screen JSON only; no rendered clip exists for this episode, do not reuse another | "Nemotron, an NVIDIA model on Nebius Token Factory, proposed the constraint and a hypothesis. Its first quote was not verbatim, so the validator refused it. The accepted hypothesis ran in simulation: finger on the floor. The model proposes; deterministic physics decides." |
| 2:00-2:25 | Release Gate: v1 BLOCKED with four reasons; v2 ELIGIBLE; fault table | screen recording of `/release`, `evidence/G11/push-dls-ik-v2_on_reg-ce-act-020-minimized.mp4` | "The release gate blocks v1 on its own stored counterexample and two held-out cases. A repaired v2 passes the suite. Nine injected faults all fail closed." |
| 2:25-2:40 | Failure Atlas + comparison curves; G12 table | screen recording of `/atlas`, `evidence/G10/comparison.svg`, README table | "Same budget, same oracle: active search found closer failures than random. The repaired v2 is eligible, and the next search round still broke it at 182 ms. That is the next regression test." |
| 2:40-2:50 | architecture slide | one static frame: search -> oracle -> minimize -> store -> gate | "Skuld: what your robot policy owes before it ships." |

## Facts the narration may use (all EXECUTED, with source)

- 3 nominal runs, PASS, byte-identical: `evidence/G07/nominal_runs.csv`, `evidence/G12/g12_report.json`.
- Random: 3 failures / 25, first at 16, nearest 0.885: `evidence/G07/metrics.json`.
- Active: 6 failures / 25, first at 6, nearest 0.781: `evidence/G10/comparison.json`.
- Minimized counterexample: delay 140.0 ms, others nominal, distance 0.700, 3/3 replays identical: `evidence/G10/counterexample.json`, `g10_report.json`.
- Tavily request id `8910bea1-...`, 5 results, constraint 3 kg approved by Adam Crozier: `evidence/G08/`.
- Nemotron (`nvidia/Nemotron-3_5-Lightning` via `npa workbench token-factory generate`, 2 calls): constraint 3 kg from the datasheet snippet, hypothesis delay 100 to 200 ms; first call's quote rejected as not verbatim; executed corner SAFETY_FAIL: `evidence/G04/generate_call.json`, `scenario.result.json`.
- Release: v1 BLOCKED (2 regression + 2 held-out SAFETY_FAIL), v2 ELIGIBLE, 9/9 faults fail closed: `evidence/G11/g11_report.json`.
- G12 rerun: v1 reproduces G07/G10 25/25 + 25/25; v2 random 1/25, active 7/25, nearest 1.013 at 182 ms delay: `evidence/G12/g12_report.json`.

## Words not to use

certified, safe, proven, global minimum, causal, learned (for this controller), GR00T. Nemotron may be named for the G04 step only, with its model id, as "proposed" or "authored", never as deciding anything.

## Recording notes

- 640x480 simulator clips: place them in a 1280x720 frame with the record card beside them rather than upscaling.
- The storyboard needs 60 s of visibly operating modules: clips at 0:00, 0:35, 0:58, 2:00 alone give 52 s of simulator footage; the ledger and gate recordings cover the rest.
- G04 segment (1:43-2:00): show the model id `nvidia/Nemotron-3_5-Lightning` on screen from `generate_call.json`; keep the rejected attempt visible for at least 3 s, it is the honest part. Spend: two calls, under one cent, estimated (npa reports no usage); say nothing about cost on camera.
- Running time by row: 12 + 23 + 23 + 27 + 18 + 17 + 25 + 15 + 10 = 170 s = 2:50. If the recording runs long, cut the atlas row to 10 s before touching the G04 row.
- Say "in simulation" once, early, and let the on-screen footer ("tested simulation envelope") carry it afterwards.
