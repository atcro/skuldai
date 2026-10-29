# G10 | Adversarial optimizer + minimizer

```yaml
schema_version: skuld.gate-report.v1
gate: G10
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, sim venv ~/.venvs/skuld-mujoco (mujoco 3.17.0), EGL rendering for the two videos; protocol 6c2b89e73525..., scene 66b5b39e65db..., policy push-dls-ik-v1 source 528a4cf61bd7... (all identical to G07, checked by the runner before anything ran)'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g10_run.sh'   # ruff, pytest, scripts/g10_run.py with --hypothesis evidence/G08/hypothesis.json
evidence_paths:
  - evidence/G10/protocol_sha256.txt            # equals evidence/G07/protocol_sha256.txt
  - evidence/G10/policy_manifest.json
  - evidence/G10/active_search.json             # full SearchResult: config, every candidate, curve, metrics
  - evidence/G10/active_ledger.csv              # 25 rows, one per candidate: phase, move, parent, values, verdict, accepted
  - evidence/G10/active_curve.csv
  - evidence/G10/active_hyp_search.json, active_hyp_ledger.csv, active_hyp_curve.csv   # exploration seeded by the approved G08 hypothesis box
  - evidence/G10/comparison.json                # G07 random vs active vs active+hypothesis, same protocol digest
  - evidence/G10/comparison.svg                 # the two curves per strategy, drawn from the CSVs
  - evidence/G10/minimization.json              # MinimizationResult: confirm, revert, refine, probe, every candidate
  - evidence/G10/minimize_ledger.csv            # 10 rows
  - evidence/G10/counterexample.json            # Counterexample: original, minimized, removed/kept, replay seeds and outcomes
  - evidence/G10/active/, active_hyp/, minimize/, replay/   # every episode: gzipped Trajectory + oracle EpisodeResult
  - evidence/G10/original_failure.mp4           # act-020 rendered (376 frames, 15 s)
  - evidence/G10/minimized_failure.mp4          # minimized scenario rendered (376 frames, 15 s)
  - evidence/G10/manifest.json                  # SHA-256 of all 146 files above
  - evidence/G10/g10_report.json
  - evidence/G10/tests-sim-venv.txt
  - evidence/G10/g10_run.log
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (sim venv): 65 passed in 2.08s, exit 0 (2 new: search mechanics on a synthetic objective)'
  - 'scripts/g10_run.py: 25 + 25 search episodes, 10 minimization episodes, 3 replays, 2 rendered episodes; reproduced=true; exit 0'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G11: release state machine fail-closed, regression registry seeded with counterexample.json, held-out suite on evidence/G07/heldout_configs.json, fault-injection tests, 4 HTML surfaces on these records.'
```

## What was run (EXECUTED 2026-10-28 evening local / 2026-10-29 UTC)

Everything the search is judged against was locked in G07 and is unchanged:
the runner compares the protocol digest, policy source hash and scene hash to
`evidence/G07/g07_report.json` and refuses to start on any mismatch. The G07
random baseline was **not** re-run; its archived curve is read as-is.

### Search method (PROPOSED algorithm, `skuld/search/active.py`, id `explore-then-contract-v1`)

Two phases on one budget of 25 episodes, driven by one seeded NumPy generator
(sampler seed 20261027, from the protocol):

1. **Explore**: uniform samples from the domain until the first valid failure.
   Statistically the same as the random baseline.
2. **Contract**: keep the nearest failing scenario (the incumbent) and bisect
   along the ray from it to nominal (`contract` move: a failure shrinks the
   distance by the factor `a`, a pass raises the known-pass bound). Every third
   step, and whenever the ray is exhausted, propose a Gaussian `jitter` around
   the incumbent with a step size that widens on success and narrows otherwise.
   A candidate is accepted only if it is a valid failure *and* strictly closer
   to nominal.

No model, gradient or surrogate. Every candidate, accepted or not, is a ledger
row with its parent and the move that produced it. EXEC_ERROR episodes would be
logged and not counted (none occurred).

### Matched comparison (spec 8.1, same domain, oracle, policy and budget)

| Metric (budget 25) | Random (G07, archived) | Active, no prior | Active + G08 hypothesis box |
|---|---|---|---|
| Episodes to first valid failure | 16 | **6** | 1 |
| Valid failures within budget | 3 | **6** | 12 |
| Min distance from nominal among failures | 0.885 | **0.781** | 0.785 |
| Wall-clock to first failure | 8.8 s | 2.5 s | 0.5 s |
| Status counts | 22 PASS, 3 SAFETY_FAIL | 19 PASS, 6 SAFETY_FAIL | 13 PASS, 12 SAFETY_FAIL |
| Total wall-clock | 14.1 s | 10.0 s | 10.9 s |

The middle column is the protocol's comparison. The active run found its first
failure on episode 6 (act-005, distance 1.061) and then contracted through
act-007 (0.796), act-017 (0.787) and act-020 (0.781). Of its 19 contract-phase
episodes, 10 were `contract` moves and 9 `jitter`; one improvement came from a
contract (act-007) and two from jitters (act-017, act-020), so the ray
bisection alone would have stalled at 0.796 and the jitter did the rest.

The right column is **not** the matched comparison: its exploration was
restricted to the approved G08 hypothesis box (mass 0.4 to 0.5 kg, delay 150 to
200 ms), so it carries prior knowledge from G07 and the Tavily-sourced
constraint. It is reported because it is the G08 chain feeding search, which is
the product's intended loop. It found a failure on its first episode and twelve
in total, but its nearest failure (0.785) is not closer than the unprimed run's.

**Honest reading.** One run per strategy at a budget of 25. The direction
agrees with the hypothesis in spec section 3 (fewer episodes to first failure,
closer failures), but the first-failure gap is one uniform-random draw against
another and is not statistically meaningful; the min-distance gap is the
contraction phase doing what it is built to do once any failure exists. The
claim this gate supports is: *under this protocol, in this run, active search
found a closer failure than random with the same budget.* Nothing more.

### Minimization (spec 7.5, `skuld/search/minimize.py`)

Input: act-020, the nearest active failure, with all four variables perturbed
(offset -0.015 m, mass 0.170 kg, friction 0.359, delay 140.0 ms; distance 0.781).
Ten episodes, all in `minimize_ledger.csv`:

| Step | Candidate | Verdict | Decision |
|---|---|---|---|
| confirm | act-020 re-run | SAFETY_FAIL | proceed |
| revert offset to 0.0 | | SAFETY_FAIL | removed |
| revert mass to 0.1 kg | | SAFETY_FAIL | removed |
| revert friction to 0.6 | | SAFETY_FAIL | removed |
| revert delay to 0 ms | | PASS | kept |
| bisect delay 70.0, 105.0, 122.5, 131.3 ms | | PASS x4 | pass bound 131.3 ms |
| monotonicity probe at 65.6 ms | | PASS | no non-monotonicity observed on this axis |

Result: **a delay of 140.0 ms with every other variable nominal fails**
(distance 0.700, down from 0.781). Three of four perturbations were irrelevant
to this failure. Variables were reverted nearest-to-nominal first, by
normalized deviation. The order and the acceptance threshold (fail on every
seed in the seed set, here one seed because the simulator is deterministic)
were fixed in code before the run.

Failure signature of the minimized scenario (oracle): `NEVER collision`, left
finger on the floor from t = 3.42 s, 11 control steps, peak normal 11.4 N
(reported, no limit claimed). The block still reached the target at 7.28 s.
This is the same signature as G05 `delay_200`, the three G07 random failures
and the G08 hypothesis corner, and it is now isolated to one variable.

### Replay and reproducibility (spec 7.6)

The minimized scenario was run on seeds 0, 1 and 2: three SAFETY_FAIL verdicts
and three byte-identical step sequences (one SHA-256 for all three, recorded in
`g10_report.json`). The simulator ignores the seed, so this is a determinism
and reproducibility check, not a failure-probability estimate, and the
`Counterexample` record says so. Approved wording: *a locally minimized,
reproducible failure under our tested simulator and controller.* Not a global
minimum; not a causal proof; not a statement about the real robot.

Both the original (act-020) and the minimized scenario were rendered from
separate runs of the same scenarios; both rendered runs are judged SAFETY_FAIL
by the oracle.

## Acceptance check (spec 13.1 G10 row)

| Requirement | Result |
|---|---|
| `Objective(x)` | `scripts/g10_run.py` closure: run, store, judge with the oracle; the search sees only `EpisodeStatus` and the domain distance |
| Inspectable bounded search | explore-then-contract, two moves, documented in the module; stays inside the domain (checked on every candidate); unit test asserts bounds, seeding, budget |
| Matched budgets | 25 vs 25, same protocol digest, same policy and scene hashes (runner refuses otherwise); random curve read from the archive |
| Every candidate logged | 25 + 25 + 10 + 3 ledger rows and stored episodes; `accepted` and `parent` columns reconstruct the decision path |
| A real failure found | 6 in the matched run, nearest 0.781 |
| Greedy-revert + local refinement | 3 variables reverted, 1 kept, 4 bisections, 1 monotonicity probe |
| Repeated on seed set | 3 of 3 replays fail, bit-identical |
| Both scenarios + replay footage persisted | `counterexample.json`, `original_failure.mp4`, `minimized_failure.mp4`, 146 hashed files |
| Report no-advantage honestly | not needed this run; the honest-reading paragraph above bounds the claim |

## Honest limits

- Budget 25 is small (protocol note); no repeat runs across sampler seeds were
  made, so no variance estimate exists. A fair follow-up is several seeds per
  strategy, which costs about 15 s per 25 episodes and can be done in G12 if
  time allows.
- The contraction phase assumes failure is monotone along a ray toward nominal;
  jitters and the minimizer's probe are the only hedges. The pass bound of
  131.3 ms is a bisection bound on one axis with the other variables nominal,
  not a threshold claim.
- Hypothesis seeding used a human-authored hypothesis (G08). Nemotron authoring
  still waits on G04.
- The regression seed list in the protocol is still empty; G11 registers the
  counterexample as the first stored regression test.

## Cost and approval

No spend, no network. About five minutes of laptop time: 63 unrendered
episodes in about 35 s, two rendered 15 s videos in 89 s and 105 s.
