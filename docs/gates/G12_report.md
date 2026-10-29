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

Second pass, 2026-10-29 evening local, on commit `f58fa64` (G04 merged, tests
consolidated to 69). Each row names what was re-checked on that commit, not
copied from the first pass.

| # | Question | Finding (re-verified on f58fa64) | Blocking? |
|---|---|---|---|
| 1 | Does the policy action truly control physics each timestep? | Yes. `skuld/sim/episode.py` `run_episode` calls `policy.act(obs)`, `adapter.act(action)`, `adapter.step()` in that order every control step; `test_action_actually_moves_the_arm` and `test_replay_is_bit_identical_for_fifty_steps` ran green in the sim venv on this commit. No recording is ever presented as a policy. | no |
| 2 | Do perturbations actually affect observations or dynamics? | Yes. The four MuJoCo adapter tests (mass into the compiled model, friction on both geoms, offset into `qpos`, delay into the observation buffer) passed on this commit. The archived ledgers show delay as the dominant axis; the other three change outcomes at the margin. | no |
| 3 | Are all pass/fail outcomes simulator-derived? | Yes. `skuld/oracle`, `skuld/release` and `skuld/search` import nothing from `skuld/integrations`; the oracle is a function of the recorded trajectory and the approved spec. The G04 Nemotron output reaches the simulator only as a scenario inside the locked domain, never as a verdict. | no |
| 4 | Is the random baseline fairly budgeted? | Yes. Same domain, 25 episodes each, random archived (G07) before active search existed; `scripts/g10_run.py` and `g12_run.py` refuse to start on a protocol, policy or scene hash mismatch. Caveat stated in README: one run per strategy. | no |
| 5 | Can the minimized failure be replayed within stated tolerance? | Yes. `evidence/G10/g10_report.json` replay block: 3/3 SAFETY_FAIL with one identical `steps_sha256`; tolerance zero because the simulator is deterministic and the seed is inert (stated in the record). | no |
| 6 | Are held-out tests uncontaminated by search or repair? | Yes. The five held-out scenarios come from `skuld/core/protocol.py` seeds 1000 to 1004, fixed in G07 before any search; no search, minimization or repair step read them; v2 was designed from the G10 counterexample. | no |
| 7 | Are Nemotron / Nebius / Tavily claims proven by runtime artifacts? | Yes. Tavily: `evidence/G08/tavily_search.json` with request id. Nemotron / Token Factory: `evidence/G04/generations.jsonl` and `generate_call.json` (two `npa workbench token-factory generate` calls to `nvidia/Nemotron-3_5-Lightning`, nonempty completions, sha256 recorded; catalog request id in `models_list.json`). Stated limits: npa gives no provider request id or usage for `generate`; temperature 0 did not repeat across the two calls; one call was rejected by the validator and kept. README, video script and this report say exactly this. | no |
| 8 | Are failed or unknown cloud jobs fail-closed? | No cloud jobs exist. `evidence/G11/fault_injection.json` `failed_job` (EXEC_ERROR, job status unknown) yields ERROR; `missing_case` INCOMPLETE; `corrupt_artifact`, `stale_policy_hash`, `spec_mismatch` ERROR; `injected_pass_verdict` refused by the schema. 9/9 as expected; 13 parametrised gate faults in `tests/test_release.py`. | no |
| 9 | Are keys, licenses and public assets safe? | Yes on the repository side. Full-history `git grep` across all revisions for both key prefixes, bearer tokens, `tvly-`, `sk-`, `AKIA`, `ghp_` and private-key headers: 0 hits outside the redaction code and its tests. `.env` and `.env.*` git-ignored, no tracked credential files, LICENSE Apache-2.0, Menagerie Panda licence copied in `evidence/G05`. Repo is still private, which is correct until a human flips it. **CI status for f58fa64 is UNKNOWN from this machine** (`gh` not installed): the human checks the Actions tab before flipping public. | no (CI check is a human step) |
| 10 | Does the video honestly show functioning modules for >= 60 s, under 3:00? | **Not recorded.** `docs/video_script.md` is at 2:50 with a G04 segment at 1:43-2:00; the simulator clips alone give 52 s and the ledger and gate recordings cover the rest; every clip is an archived artifact and no clip exists for the G04 episode (the script forbids borrowing one). | **yes, until recorded** |

Cross-checks made on this pass: every number in the README results tables
matches `evidence/G12/g12_report.json` (3/25/25 episodes; failures 0/3/6 for v1
and 0/1/7 for v2; first failure 16 vs 6 and 17 vs 6; nearest 0.885 vs 0.781 and
1.262 vs 1.013; reproduction 25/25 and 25/25). No banned wording in README, the
video script or the G04 report ("global minimum" and "causal" appear only as
negations). `docs/rules.md` R3 and R4 boxes are still unticked: that is the
human's confirmation on Devpost, now with an artifact to point at.

One blocking finding remains: (10) record the video from
`docs/video_script.md` with the dashboard served from this commit. Before the
public flip, the human also reads the CI result for `f58fa64` on GitHub.

## Honest limits carried into the submission

Simulation only, one scene, one classical controller, budgets of 25, one run
per strategy, one failure mechanism observed, minimization local, Nemotron
proposes only (validated, human-approved, never deciding) and its temperature-0
output did not repeat across two calls. All of these are in the README's
Limitations section in the same words.

## Cost and approval

No spend, no network beyond the earlier single Tavily call. About four minutes
of laptop time for the final rerun and smoke.
