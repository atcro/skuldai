# G07 | Baselines, seeds, experimental design

```yaml
schema_version: skuld.gate-report.v1
gate: G07
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, Python 3.12.3, sim venv ~/.venvs/skuld-mujoco (mujoco 3.17.0), EGL rendering for the one video; scene 66b5b39e65db..., policy push-dls-ik-v1 source 528a4cf61bd7...'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g07_run.sh'   # ruff, pytest, scripts/g07_run.py
evidence_paths:
  - evidence/G07/protocol.json                 # the locked protocol (PROTOCOL_V1)
  - evidence/G07/protocol_sha256.txt           # 6c2b89e735255c64cb358e716aed453debff5d3be30759e5620a73872486c909
  - evidence/G07/heldout_configs.json          # 5 reserved configurations, never searched
  - evidence/G07/policy_manifest.json
  - evidence/G07/nominal_runs.csv              # 3 nominal runs
  - evidence/G07/random_baseline.csv           # 25 uniform-random episodes, one row each
  - evidence/G07/random_baseline_curve.csv     # failures found and running min distance vs cumulative episodes
  - evidence/G07/metrics.json                  # the predefined primary metrics
  - evidence/G07/nominal/, random/, spotcheck/ # every episode: gzipped Trajectory + oracle EpisodeResult
  - evidence/G07/first_random_failure.mp4      # rand-015, rendered from a separate run of the same scenario
  - evidence/G07/manifest.json                 # SHA-256 of all 71 files above
  - evidence/G07/g07_report.json
  - evidence/G07/tests-sim-venv.txt
  - evidence/G07/g07_run.log
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (sim venv): 60 passed in 2.29s, exit 0 (51 contract/oracle/protocol + 9 MuJoCo)'
  - 'scripts/g07_run.py: 3 nominal + 25 random + 3 spot-check/video episodes, exit 0'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G08 Tavily evidence step (live search, DocumentedConstraint, approval before any bound changes). Then G10 active search + minimization against this baseline, same budget (25), same domain, same oracle.'
```

## Locked protocol (spec 8.1 step 1; `skuld/core/protocol.py`, EXECUTED 2026-10-26)

Fixed before any search strategy exists. SHA-256 recorded above and in every
G10 result that cites it.

| Item | Value |
|---|---|
| Domain | `push-v1`: object_offset_m [-0.10, 0.10], object_mass_kg [0.05, 0.5], friction_coefficient [0.2, 1.0], observation_delay_ms [0, 200]; **all distance weights 1.0** (published in `protocol.json`) |
| Distance | weighted normalized L2 (spec 7.2) |
| Spec | `push-block-v1`, sha256 `0078d552...`, approved by Adam Crozier 2026-10-26 |
| Policy | `push-dls-ik-v1` (classical), source sha256 `528a4cf6...` |
| Seeds | nominal [0, 1, 2]; held-out [1000..1004]; regression [] (filled by G10) |
| Sampler seeds | random baseline 20261026; active search 20261027; held-out configs 1000 |
| Held-out configurations | 5 scenarios sampled with seed 1000, ids `heldout-000..004`, reserved for release evaluation (G11); excluded from search and repair |
| Budget | N_nominal = 3, N_random = 25, N_active = 25 (from measured throughput, below) |
| Primary metrics | episodes to first valid failure; valid failures within budget; min distance from nominal among valid failures; wall-clock to first failure; the two curves vs cumulative episodes |

Why 3 nominal runs and not 5 to 10: the simulator and policy are
deterministic (G05 bit-identical replay, confirmed again here: the three
nominal trajectories are byte-identical in their steps). A scenario fails 0 or
1 times out of 1; repeating it adds no information, only compute (spec 12.2).

## Random baseline (EXECUTED, 25 episodes, unrendered)

| Metric | Value |
|---|---|
| Status counts | 22 PASS, 3 SAFETY_FAIL, 0 TASK_FAIL, 0 INVALID, 0 TIMEOUT, 0 EXEC_ERROR |
| Episodes to first valid failure | 16 (rand-015) |
| Valid failures within budget | 3 |
| Min distance from nominal among failures | 0.885 (rand-015) |
| Wall-clock to first failure | 8.8 s |
| Total wall-clock, 25 episodes | 14.1 s (mean 0.56 s per 15 s episode) |

The three failures, from `random_baseline.csv`:

| Episode | offset (m) | mass (kg) | friction | delay (ms) | distance | Verdict |
|---|---|---|---|---|---|---|
| rand-015 | -0.022 | 0.282 | 0.729 | 152 | 0.885 | SAFETY_FAIL: finger on floor from t = 3.52 s, 14 control steps |
| rand-016 | +0.059 | 0.390 | 0.984 | 185 | 1.262 | SAFETY_FAIL: finger on floor, first at step 173 |
| rand-024 | -0.072 | 0.298 | 0.531 | 180 | 1.068 | SAFETY_FAIL: finger on floor, first at step 212 |

All three failures have observation delay at or above 152 ms; 21 of the 22
passes have delay at or below 138 ms, and one pass (rand-001) has 194 ms. So
delay is the dominant factor in this sample but not a clean threshold: the
other variables matter at the margin. That is what G10's search and
minimization are for. No claim is made beyond this sample of 25 under this
simulator and controller.

Note that the three random failures are all farther from nominal (0.885 and
up) than the hand-picked G05 probe `delay_200` (distance 1.000) is close to
them. The nearest failure found so far by any means is rand-015 at 0.885. The
baseline G10 must beat is: 1 failure per 8.3 episodes, nearest at 0.885.

## Spot-check and evaluator agreement (spec 8.1 step 7)

- rand-015 (first failure) and rand-000 (first pass) were re-run from their
  stored scenarios in the same process: both trajectories bit-identical to the
  stored ones, both verdicts identical.
- rand-015 was run a third time with rendering on, producing
  `first_random_failure.mp4` (376 frames, 15 s at 25 fps); the oracle verdict
  on that rendered run is also SAFETY_FAIL.
- Rendering does not change physics (same scene, same control; rendering reads
  state, it does not write it), and the verdict agreement above is consistent
  with that; byte-level equality of the rendered run was not checked.

## Acceptance check (runbook G07, spec 13.1)

| Requirement | Result |
|---|---|
| Locked protocol | `PROTOCOL_V1`, hashed, written to evidence; test asserts it rebuilds identically |
| Seed partition + held-out configs | nominal / held-out seed lists disjoint; 5 held-out configurations stored and reserved |
| 3 to 10 nominal runs | 3, all PASS, byte-identical steps (determinism re-confirmed) |
| Budget from throughput | 0.56 s per unrendered 15 s episode measured here; 25 + 25 episodes is under a minute; stated as a small-sample limitation |
| Fixed RNG | `numpy.random.default_rng(sampler_seed)`; test asserts same seed gives same scenarios, different seed differs |
| All episodes stored | 31 episodes, each with gzipped `Trajectory` and `EpisodeResult`, 71 files hashed in `manifest.json`; nothing discarded, no retries occurred |
| Distance weights published | in `protocol.json` (`domain.variables[].weight`, all 1.0) |
| Metrics predefined | `protocol.primary_metrics`, written before the baseline ran |
| Random baseline run and spot-checked | above |

## What changed in the runner during this gate, and why

The first G07 attempt reported 6 failures: the same 3 safety failures plus 3
`TASK_FAIL` verdicts of the form "block reached the target but left it". The
episode runner (from G05) stopped recording 0.5 s after the goal check fired,
while the block was still sliding and, in rand-002, while the arm had already
climbed back to approach height to re-push (it moved 10 cm in the last 25
recorded steps). The verdict depended on where the recording was cut. Two
fixes, both now in `skuld/sim/episode.py`:

1. a first attempt stopped when the block came to rest; that still cut a
   recovery in progress, so it was replaced by
2. **every episode is recorded for the full spec deadline (15 s)**. The oracle
   judges the state at the deadline and nothing else.

With full recordings those three episodes recover and PASS. The G05 evidence
(recorded with the 0.5 s cut) stays as it is: its nominal verdicts hold and
its two safety failures occur long before any cut. The runner change costs
about 0.3 s per unrendered episode and makes rendered videos 15 s long.

Negative result worth stating: the "block left the target" failure mode seen
in the first attempt was an artifact of the harness, not of the policy. It is
recorded here so nobody rediscovers it as a finding.

## Cost and approval

No spend. No network. About five minutes of laptop time per full run,
dominated by the single 15 s video (114 s to render) rather than by the 31
unrendered episodes (about 17 s together).
