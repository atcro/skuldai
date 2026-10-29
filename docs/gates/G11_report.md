# G11 | CI/CD release decision + UI

```yaml
schema_version: skuld.gate-report.v1
gate: G11
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, sim venv ~/.venvs/skuld-mujoco (mujoco 3.17.0), EGL for the one video; evidence produced at commit ada1953 (recorded in every candidate); protocol 6c2b89e73525..., spec 0078d5522508...'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g11_run.sh'   # ruff, pytest, scripts/g11_run.py
  - 'uvicorn skuld.api.main:app --host 127.0.0.1 --port 8765'            # dashboard; the four surfaces are also rendered by tests/test_release.py over this evidence
evidence_paths:
  - evidence/G11/policy_registry.json           # push-dls-ik-v1 and push-dls-ik-v2, kind classical, source hashes
  - evidence/G11/test_suite.json                # 3 nominal + 2 regression (from evidence/G10/counterexample.json) + 5 held-out
  - evidence/G11/candidate_push-dls-ik-v1.json, candidate_push-dls-ik-v2.json   # ReleaseCandidate with commit sha, sim version, suite ref, seed lists
  - evidence/G11/release_push-dls-ik-v1.json    # BLOCKED, 4 reasons
  - evidence/G11/release_push-dls-ik-v2.json    # ELIGIBLE
  - evidence/G11/push-dls-ik-v1/<suite>/, push-dls-ik-v2/<suite>/   # every episode: gzipped Trajectory + oracle EpisodeResult (20 episodes)
  - evidence/G11/fault_injection.json           # 9 injected faults, each decision saved in fault_injection/<fault>.release.json
  - evidence/G11/push-dls-ik-v2_on_reg-ce-act-020-minimized.mp4   # repaired policy on the minimized counterexample (oracle PASS)
  - evidence/G11/manifest.json                  # SHA-256 of 51 files
  - evidence/G11/g11_report.json
  - evidence/G11/tests-sim-venv.txt
  - evidence/G11/g11_run.log
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (sim venv): 80 passed in 2.15s, exit 0 (15 new: suite registry, 13 gate fault cases, 4 dashboard surfaces rendered over this evidence)'
  - 'scripts/g11_run.py: 20 suite episodes + 1 rendered; v1 BLOCKED, v2 ELIGIBLE; 9/9 faults fail closed; exit 0'
  - 'CI: .github/workflows/ci.yml runs ruff + pytest on push to main (app venv, no simulator). Run status for the commit carrying this report: UNKNOWN from here (private repo; confirm at https://github.com/atcro/skuldai/actions)'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G12: freeze code, rerun nominal/random/active on the frozen policy, README results table from evidence, video (<3:00, >=60 s of real modules), secret scan, LICENSE check, flip public, Devpost + YouTube (human). Human items still open: G00 Devpost confirmation, G03 credits, G04 Nemotron call, CI run URL, screen recording of the dashboard.'
```

## What the gate is (EXECUTED 2026-10-28 evening local / 2026-10-29 UTC)

`skuld/release/gate.py::decide` is a pure function of a `ReleaseCandidate`, a
`TestSuite` and whatever evidence exists per scenario. It runs nothing and
trusts nothing it cannot check. Precedence when several things are wrong:

```
ERROR > BLOCKED > INCOMPLETE > ELIGIBLE
```

| Status | Produced when |
|---|---|
| ERROR | artifact behind a result missing, unreadable, schema-refused or checksum mismatch; INVALID or EXEC_ERROR verdict; result names a different policy, scenario or spec than the candidate; results for scenarios not in the suite; candidate names a different suite |
| BLOCKED | any TASK_FAIL or SAFETY_FAIL in a required suite |
| INCOMPLETE | a required scenario has no result, or its recording ended before the deadline (TIMEOUT) |
| ELIGIBLE | every scenario of nominal, regression and held-out has a verified PASS |

The `ReleaseDecision` schema (G02) independently refuses an ELIGIBLE without
all three suites or with a failing regression, so the gate and the contract
have to agree before anything green exists. "Eligible" means "passed the named
simulation suite", never "safe".

## Registries

- **Policies** (`policy_registry.json`): `push-dls-ik-v1`, kind `classical`,
  source sha `528a4cf6...` (unchanged since G05); `push-dls-ik-v2`, kind
  `classical`, source sha `123997db...` over both v1 and v2 source files. The
  schema refuses to call either GR00T or learned.
- **Test suite** (`test_suite.json`, ref `skuld-push-protocol-suite-97c97ea27eb0`,
  content-addressed): nominal `nominal-s0..2` from the protocol; regression
  `reg-ce-act-020-minimized` and `reg-ce-act-020-original` built from
  `evidence/G10/counterexample.json` (a counterexample that never failed on
  replay is refused as a regression test); held-out `heldout-000..004`, the
  protocol's reserved configurations, never searched or repaired against.

## Release decisions (same suite, same oracle, same commit)

| Suite | Scenario | delay (ms) | v1 (policy under test) | v2 (repair) |
|---|---|---|---|---|
| nominal | nominal-s0, s1, s2 | 0 | PASS, PASS, PASS | PASS, PASS, PASS |
| regression | reg-ce-act-020-minimized | 140.0 | **SAFETY_FAIL** | PASS |
| regression | reg-ce-act-020-original | 140.0 | **SAFETY_FAIL** | PASS |
| held_out | heldout-000 | 40.6 | PASS | PASS |
| held_out | heldout-001 | 150.7 | **SAFETY_FAIL** | PASS |
| held_out | heldout-002 | 49.7 | PASS | PASS |
| held_out | heldout-003 | 56.1 | PASS | PASS |
| held_out | heldout-004 | 179.8 | **SAFETY_FAIL** | PASS |
| **Decision** | | | **BLOCKED** (4 reasons) | **ELIGIBLE** |

v1 is blocked by its own stored counterexample and, independently, by two
held-out configurations it had never seen. Every reason names the suite,
scenario, verdict and rule (`NEVER collision`).

## Repair attempt (spec 7.7, one concrete change, labelled)

Diagnosis from G10: the minimized failure is observation delay alone, and the
signature is a finger on the floor during descent. v1 closes the loop on the
*observed* height and descends at up to 0.25 m/s, so with 140 ms of delay it
believes it is about 3.5 cm higher than it is, more than the 2.5 cm push height.

`push-dls-ik-v2` (`skuld/policies/push_controller_v2.py`) changes two things:
vertical speed capped at 0.05 m/s below 6 cm (about 1 cm of overshoot at 200 ms),
and push height 3.0 cm instead of 2.5 cm. The v1 file is untouched so every
stored v1 result keeps a valid hash. v2 passes all ten scenarios, including both
regressions and the two held-out delays of 151 and 180 ms, and the rendered run
on the minimized counterexample is judged PASS by the oracle (video above).

What this does and does not show: a changed policy was re-tested against the
complete suites and the gate's verdict flipped on evidence, which is the CI/CD
loop. It does not show that v2 is robust in general: ten scenarios under one
simulator and controller. A G12 rerun of random and active search against v2
would say more, and may well find a new failure.

## Fault injection (spec 9, 15; `fault_injection.json`, all 9 fail closed)

| Fault | Injected | Decision | Expected |
|---|---|---|---|
| known_safety_violation | the real v1 evidence | BLOCKED | BLOCKED |
| missing_heldout_case | heldout-004 result removed from the v1 record | BLOCKED | BLOCKED (outranks INCOMPLETE) |
| missing_case_on_green_record | regressions forced to PASS, held-out cases removed | INCOMPLETE | INCOMPLETE |
| corrupt_artifact | nominal-s0 trajectory truncated to half its bytes, checksum mismatch | ERROR | ERROR |
| stale_policy_hash | candidate names push-dls-ik-v0, results are v1's | ERROR | ERROR |
| failed_job | heldout-000 replaced by EXEC_ERROR "job status unknown" | ERROR | ERROR |
| truncated_recording | nominal-s0 cut at step 100, oracle says TIMEOUT | BLOCKED | BLOCKED (v1 regressions still fail) |
| injected_pass_verdict | regression result edited to PASS with violations kept | ERROR (schema refused the file) | ERROR |
| spec_mismatch | nominal-s0 result claims spec push-block-v0 | ERROR | ERROR |

The first attempt of this run returned BLOCKED for `injected_pass_verdict`
because a schema-refused file was treated as "not executed" and the other
regression failure outranked it. Still fail-closed, but the wrong reason. The
gate now checks for an unusable artifact before the missing-result branch and
reports ERROR with the validation message; the unit test covers it. Recorded
here so the change is visible.

The thirteen gate cases in `tests/test_release.py` run the same matrix against
a synthetic all-green record, where each fault is isolated (there, a missing
case yields INCOMPLETE and a timeout yields INCOMPLETE on their own).

## Dashboard (spec 11: four surfaces, read-only, real records)

FastAPI + Jinja, no build step, served from `evidence/`. Any missing record is
listed in an on-screen warning box instead of being filled in.

| Surface | Route | Shows (source) |
|---|---|---|
| Test Lab | `/` | policy and hash, 1 local worker, 25/25 episodes, 6 failures vs 3 random, nearest 0.781 vs 0.885, comparison curves, latest video, full active ledger (G10) |
| Failure Atlas | `/atlas?x=&y=` | all 85 stored episodes from G07 and G10 over two chosen variables, pass/fail colours, minimized counterexample ring, M(π) = nearest *observed* failure distance 0.700, with the on-screen note that points are observations and no boundary is fitted |
| Counterexample Replay | `/counterexample` | original vs minimized values, removed vs kept, replay seed set 3/3 with the determinism note, both videos, minimizer ledger (G10) |
| Release Gate | `/release` | per-suite verdicts for v1 and v2, status, reasons, candidate and suite hashes, repair video, suite registry, fault-injection table (G11) |

The test `test_dashboard_surfaces_render_from_real_records` renders all four
over this evidence and asserts the v1 card never shows ELIGIBLE. A human screen
recording of the running server is a G12 item.

## Honest limits

- The CI workflow runs lint and unit tests only (no simulator, no secrets, by
  design). Its run URL for this commit is not verifiable from this session.
- The suite is small: 3 + 2 + 5 scenarios. The held-out set is 5 random
  configurations reserved in G07; two of them happen to be high-delay cases,
  which is why they catch v1.
- v2 is a heuristic fix for one mechanism, evaluated on ten scenarios. It is
  "eligible under the named suite", nothing more.

## Cost and approval

No spend, no network. About three minutes of laptop time per run: 20 unrendered
episodes in about 10 s, one 15 s video in about 100 s.
