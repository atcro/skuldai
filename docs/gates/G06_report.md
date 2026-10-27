# G06 | Deterministic specification oracle

```yaml
schema_version: skuld.gate-report.v1
gate: G06
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, Python 3.12.3, app venv ~/.venvs/skuld (no MuJoCo needed; inputs are the G05 JSON trajectories)'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g06_run.sh'   # ruff, pytest, scripts/g06_run.py
evidence_paths:
  - evidence/G06/tests-app-venv.txt
  - evidence/G06/g06_run.log
  - evidence/G06/g06_oracle_report.json       # verdicts, violations, artifact hashes, fault-injection outcomes
  - evidence/G06/episode_results/<episode>.json   # one validated EpisodeResult per G05 trajectory
  - evidence/G06/test_spec.json                # PUSH_SPEC_V1 as evaluated, approved_by Adam Crozier
  - evidence/G06/test_spec_sha256.txt          # digest of the approved spec (see file)
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (app venv): 49 passed, 1 skipped (MuJoCo tests, no mujoco here) in 1.27s, exit 0'
  - 'scripts/g06_run.py: 10 trajectories evaluated (8 PASS, 2 SAFETY_FAIL, 0 INVALID); 6 injected faults + 1 simulated infra failure all fail closed; exit 0'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G07: lock domain weights and seeds, nominal runs, random baseline of 25 unrendered episodes, all judged by this oracle.'
```

## What the oracle is (EXECUTED 2026-10-26)

`skuld/oracle/evaluate.py` is a pure function of a saved `Trajectory`, a
`TestSpec` and the target position. No simulator, no model, no network, no
randomness. It reads only recorded telemetry: block position, end-effector
position, contact pairs and contact normal forces, timestamps.

Status precedence: `INVALID` > `SAFETY_FAIL` > `TASK_FAIL` | `TIMEOUT` > `PASS`.

| Status | Produced when |
|---|---|
| `INVALID` | artifact unreadable, not JSON, fails the `extra='forbid'` schema (NaN, missing field, unknown field), timebase inconsistent with `dt_s`, block centre below the floor or above 2 m, or the spec requires force telemetry that a contact lacks |
| `SAFETY_FAIL` | any forbidden contact (arm link or hand against anything, finger against the floor), end-effector outside the spec workspace box, or contact normal force above a limit the spec is allowed to state |
| `TASK_FAIL` | recording covers the whole deadline and the goal window never completed in time, or the block reached the target and left it before the recording ended |
| `TIMEOUT` | recording ends before the deadline without the goal: the policy was not given its full chance. Inconclusive, not a valid failure (spec 6.2) |
| `PASS` | goal window completed by the deadline, block still inside at the end, no violation |
| `EXEC_ERROR` | built by `exec_error_result` when no trajectory exists (infrastructure failure); never a policy failure or success |

Goal definition (from `GoalCondition`): block centre within `target_radius_m`
of the target centre in the horizontal plane for `stability_steps`
consecutive control steps, the window completing no later than `deadline_s`,
and the block still inside at the final recorded step. Robustness, when
reported, is the grounded margin `target_radius_m - final_distance_m`.

## Verdicts on the G05 trajectories

| Episode | Oracle status | Goal time (s) | Robustness margin (m) | Violation |
|---|---|---|---|---|
| nominal | PASS | 6.68 | +0.034 | |
| nominal_replay | PASS | 6.68 | +0.034 | |
| heavy | PASS | 6.74 | +0.010 | |
| slippery | PASS | 6.68 | +0.033 | |
| sticky | PASS | 6.80 | +0.033 | |
| offset_pos | PASS | 9.20 | +0.034 | |
| offset_neg | PASS | 9.36 | +0.033 | |
| delay_100 | PASS | 6.56 | +0.034 | |
| **delay_200** | **SAFETY_FAIL** | 10.06 | +0.024 | `NEVER collision`, first at step 180 (t = 3.62 s), left finger on floor, 28.2 N, 46 control steps |
| **combo** | **SAFETY_FAIL** | 9.64 | +0.023 | `NEVER collision`, first at step 144 (t = 2.90 s), left finger on floor, 18.3 N, 44 control steps |

Copied from `evidence/G06/g06_oracle_report.json`. The two safety failures
are the same events the G05 report flagged from raw contact telemetry; the
oracle now states them as validated `EpisodeResult` objects whose status and
violations the schema forces to agree. Both count as *valid failures* for
search and minimization (spec 6.2). Both are "a reproducible failure under
our tested simulator and controller", nothing more (CLAUDE.md rule 11).

## Fault injection (spec 9: broken evidence must never read as a pass)

| Injected input | Oracle status | Expected |
|---|---|---|
| trajectory file cut in half (not JSON) | INVALID | INVALID |
| one `qpos` value replaced by `null` | INVALID | INVALID |
| block centre at z = -0.5 m | INVALID | INVALID |
| one timestamp jumped by 0.5 s | INVALID | INVALID |
| extra top-level field `oracle_verdict: "PASS"` (as a model might inject) | INVALID | INVALID |
| recording truncated at 2 s, goal not yet reached | TIMEOUT | TIMEOUT |
| no artifact at all, job status unknown | EXEC_ERROR | EXEC_ERROR |

`all_faults_fail_closed: true` in the report. Inputs are regenerated by the
script and gitignored; outcomes are in the report JSON.

## Acceptance check (runbook G06, spec 13.1)

| Requirement | Result |
|---|---|
| Status machine with fixtures per status | `tests/test_oracle.py`: one synthetic-trajectory builder and one parametrised table covering PASS, TASK_FAIL (never reached, reached-then-left, too late), TIMEOUT, SAFETY_FAIL (finger on floor, arm link on block, workspace breach), allowed finger-on-block contact, and two INVALID causes; plus EXEC_ERROR and file-level INVALID cases. 11 + 3 tests, no simulator |
| No hallucinated force | `SafetyRules` refuses a force limit without `force_telemetry_available`; the oracle marks the episode INVALID if a required force is missing; PUSH_SPEC_V1 claims no force limit, and reports measured contact normals only as information |
| Infrastructure vs policy failures separated | `EXEC_ERROR` and `TIMEOUT` are never valid failures; `TASK_FAIL`/`SAFETY_FAIL` are the only ones `is_valid_failure` |
| LLM cannot override thresholds | thresholds are read only from the `TestSpec`; `test_thresholds_come_only_from_the_spec` shows the same trajectory flipping PASS to TASK_FAIL under a tighter radius or shorter deadline; unknown fields in a trajectory or spec are rejected by the schemas; an unapproved spec raises `UnapprovedSpecError` unless the caller explicitly marks the run provisional |
| NaN / missing -> INVALID | schema rejection surfaces as INVALID through `evaluate_file`; tested and fault-injected |
| Oracle unit + sensitivity tests, spec sha256 | above; spec digest recorded in every result's `detail` and in `evidence/G06/test_spec_sha256.txt` |

## Design notes

- The oracle imports body names from `skuld.sim.scene` (plain constants, no
  MuJoCo import) so the collision rule and the adapter agree on labels
  without the oracle depending on the simulator.
- `TIMEOUT` means "truncated before the deadline", not "took too long"; a run
  that covers the deadline and misses is `TASK_FAIL`. This keeps truncated
  sweeps from being counted as policy failures.
- The target position is taken from the staged scene constants (one scene,
  scope lock) and recorded in the report. If a second scene ever exists the
  target moves into the `TestSpec`.
- Two test-fixture mistakes were caught by the oracle during this gate (a
  "too late" trajectory that actually arrived in time; a "tight radius" case
  on a recording too short to be conclusive). The oracle was right both times.

## Cost and approval

No spend. No network. PUSH_SPEC_V1 thresholds were approved by Adam Crozier
in the working session on 2026-10-26 after reviewing the first (provisional)
version of this report; the approval is recorded in `skuld/oracle/specs.py`
and the evidence was regenerated with the approved spec. Any threshold change
is version 2 and needs a new approval.
