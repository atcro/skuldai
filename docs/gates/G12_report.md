# G12 | Final benchmark, demo, public repo, submission

```yaml
schema_version: skuld.gate-report.v1
gate: G12
status: BLOCKED        # PASS | FAIL | BLOCKED | NOT_STARTED  -- engineering side complete incl. G04 (2026-10-29); blocked only on human-only items: video, rules confirmation, public flip, submission
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, sim venv ~/.venvs/skuld-mujoco (mujoco 3.17.0; full freeze in evidence/G12/requirements.sim.freeze.txt); frozen code commit 1d11d51958dc, clean tree (evidence/G12/frozen_commit.txt)'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g12_run.sh'            # ruff, pytest, pip freeze, scripts/g12_run.py
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/dashboard_smoke.sh'    # uvicorn + curl of the four surfaces
evidence_paths:
  - evidence/G12/frozen_commit.txt                 # 1d11d51..., dirty_tree: False
  - evidence/G12/g12_report.json                   # results table source, reproduction checks
  - evidence/G12/push-dls-ik-v1/{nominal,random,active}/   # 53 episodes, gzipped Trajectory + EpisodeResult each
  - evidence/G12/push-dls-ik-v2/{nominal,random,active}/   # 53 episodes
  - evidence/G12/push-dls-ik-v*/active_search.json
  - evidence/G12/requirements.sim.freeze.txt       # 49 pinned packages
  - evidence/G12/dashboard_smoke.txt
  - evidence/G12/manifest.json                     # SHA-256 of 217 files
  - evidence/G12/tests-sim-venv.txt
  - evidence/G12/g12_run.log
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (sim venv, MuJoCo tests included): 80 passed, exit 0 (at the frozen commit; 82 after the G04 tests were added, 69 after the 2026-10-29 consolidation that removed duplicated checks, scripts/g10_check.sh)'
  - 'scripts/g12_run.py: 106 episodes; v1 random 25/25 and active 25/25 byte-identical to the G07/G10 archives; nominal byte-identical for both policies; exit 0'
  - 'secret scan: working tree and full git history grep for key patterns (tvly-, sk-, AKIA, ghp_, private keys): 0 hits; no tracked .env, .pem or credential files'
spend_approved: false
approved_by: null
blockers:
  - 'G00: hackathon rules not yet confirmed by a human on Devpost (docs/rules.md boxes unticked). R3/R4 now have a runtime artifact (G04 PASS, docs/gates/G04_report.md, commit 2e5e024); the human ticks the boxes with that evidence in hand. G03 credit balance still unchecked.'
  - 'Video not recorded (script: docs/video_script.md); dashboard screen recording not made'
  - 'Repository still private; flip to public after a human reviews the secret scan above'
  - 'Devpost project page and YouTube upload (submission owner)'
next_action: 'Human: confirm rules on Devpost, record the video from docs/video_script.md (Nemotron step included), flip the repo public after the secret scan, submit on Devpost, verify incognito. Claude: run the adversarial review again on the final commit and update this report to PASS once the human items are done.'
```

## Frozen rerun (EXECUTED 2026-10-29 UTC, commit 1d11d51, clean tree)

Same protocol (sha `6c2b89e7...`), same budgets (3 / 25 / 25), same sampler
seeds, same oracle and spec, for both registered policies. Held-out and release
decisions are not re-run; they come from G11 at the same code.

| Evaluation | v1 nominal | v1 random | v1 active | v2 nominal | v2 random | v2 active |
|---|---|---|---|---|---|---|
| Episodes used | 3 | 25 | 25 | 3 | 25 | 25 |
| Failures found | 0 | 3 | 6 | 0 | 1 | 7 |
| Episodes to first failure | - | 16 | 6 | - | 17 | 6 |
| Closest failure distance | - | 0.885 | 0.781 | - | 1.262 | 1.013 |
| Compute (s, unrendered) | 2.5 | 19.8 | 17.8 | 1.5 | 14.9 | 14.2 |

**Reproduction.** Every one of the 25 random episodes of v1 has step data
byte-identical to `evidence/G07/random/`, and every one of the 25 active
episodes to `evidence/G10/active/`. The three nominal runs are byte-identical
within each policy. So the numbers published in the README are the numbers in
the archives, re-derived on the frozen commit, not copied.

**New result on the repaired policy.** v2 was ELIGIBLE under the ten-scenario
suite in G11. Under the same 25-episode searches it is still breakable: random
found 1 failure (rand-016: delay 185 ms, mass 0.39 kg, friction 0.98, offset
+0.059 m, distance 1.262); active found 7, all with delay between 182 and 190 ms, the
nearest at distance 1.013 with delay 181.6 ms, friction 0.30, mass 0.195,
offset -0.022 m. Same signature (finger on the floor). This is reported as a
negative result for the repair and as the next regression test the loop would
store. The nearest v2 failure is farther from nominal than v1's (1.013 vs
0.781), which is consistent with the repair helping, and is one run each.

## Submission checklist (spec 16.2, rules R6, R7)

| Item | State | Owner |
|---|---|---|
| Root LICENSE (Apache-2.0) | present | done |
| README: what/why/how, real results table, limitations, versions, scripts, env vars, smoke tests, asset licenses | written from `evidence/G12`, `G10`, `G11`; see README | done (Claude), human review pending |
| Exact versions | `requirements.lock.txt` (app), `evidence/G12/requirements.sim.freeze.txt` (sim) | done |
| Asset licenses | Menagerie Panda Apache-2.0, pinned commit, copy in `evidence/G05/`; `docs/sources.md` | done |
| Secret scan before public | clean (see actual_test_results) | done; human re-check before flipping |
| Dashboard runs | `evidence/G12/dashboard_smoke.txt` | done |
| Video under 3:00, >= 60 s real modules | script in `docs/video_script.md`, clips listed with sources; not recorded | **human** |
| Public repo | private | **human** |
| Devpost page, Physical AI track, YouTube URL, repo URL | not started | **human (submission owner)** |
| Incognito verification | not started | **human** |

## Adversarial review (CLAUDE.md pre-submission checklist, run as the skeptical validation engineer)

| # | Question | Finding | Blocking? |
|---|---|---|---|
| 1 | Does the policy action truly control physics each timestep? | Yes. `run_episode` calls `policy.act(obs)` then `adapter.act`, `adapter.step` every control step at 50 Hz; the controller recomputes from the observation (G05 tests assert the action changes with the observation). Nothing is replayed as a policy. | no |
| 2 | Do perturbations actually affect observations or dynamics? | Yes. Mass and friction are written into the compiled MuJoCo model, offset into `qpos`, delay into the observation buffer (adapter tests per variable, G05). The atlas shows delay is the dominant axis; the other three change outcomes at the margin (G07/G10 ledgers). | no |
| 3 | Are all pass/fail outcomes simulator-derived? | Yes. The oracle is a pure function of the recorded trajectory and the approved spec; the search and gate read only `EpisodeStatus`. No model output anywhere in the pass/fail path. | no |
| 4 | Is the random baseline fairly budgeted? | Yes. Same domain, 25 episodes, fixed sampler seed, archived before active search existed; the G10 and G12 runners refuse to start if protocol, policy or scene hashes differ. Caveat stated everywhere: one run per strategy. | no |
| 5 | Can the minimized failure be replayed within stated tolerance? | Yes. 3/3 replays SAFETY_FAIL with identical step hashes; the tolerance is zero because the simulator is deterministic, and the record says the seed does nothing. | no |
| 6 | Are held-out tests uncontaminated by search or repair? | Yes. The 5 held-out configurations were sampled and stored in G07 before any search; no search or minimization run touched them; v2 was designed from the G10 counterexample, not from held-out results. | no |
| 7 | Are Nemotron / Nebius / Tavily claims proven by runtime artifacts? | Tavily: yes (`evidence/G08/tavily_search.json`, request id). Nemotron / Nebius Token Factory: **yes as of 2026-10-29** (`evidence/G04/generations.jsonl` and `generate_call.json`: two `npa workbench token-factory generate` calls to `nvidia/Nemotron-3_5-Lightning`, nonempty completions, sha256 recorded; `models_list.json` carries the catalog request id). Caveat stated in the G04 report: npa exposes no provider request id or token usage for `generate`. README and video script updated to match. | no (was yes before G04) |
| 8 | Are failed or unknown cloud jobs fail-closed? | No cloud jobs exist. The gate's `failed_job` fault (EXEC_ERROR, "job status unknown") yields ERROR; unit-tested and in `evidence/G11/fault_injection.json`. | no |
| 9 | Are keys, licenses and public assets safe? | Secret scan of tree and history clean; `.env` git-ignored; Tavily key never in evidence (G08 scrub documented). Licenses recorded. Repo is still private, which is correct until a human flips it. | no |
| 10 | Does the video honestly show functioning modules for >= 60 s, under 3:00? | **Not recorded.** The script totals 2:42 with about 52 s of simulator footage plus dashboard recordings; every clip is an archived artifact. | **yes, until recorded** |

Finding 7 was blocking when this review was first run (2026-10-29 morning:
no Token Factory artifact existed). It was closed the same day by G04
(`docs/gates/G04_report.md`, commit 2e5e024): pinned npa, catalog, two
`generate` calls with validated outputs (one rejected and kept), human
approval, executed scenario judged SAFETY_FAIL by the oracle. One blocking
finding remains: (10) record the video from `docs/video_script.md` with the
dashboard served from the final commit.

## Honest limits carried into the submission

Simulation only, one scene, one classical controller, budgets of 25, one run
per strategy, one failure mechanism observed, minimization local, Nemotron
proposes only (validated, human-approved, never deciding) and its temperature-0
output did not repeat across two calls. All of these are in the README's
Limitations section in the same words.

## Cost and approval

No spend, no network beyond the earlier single Tavily call. About four minutes
of laptop time for the final rerun and smoke.
