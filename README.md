# Skuld

**Falsification-driven CI/CD for embodied robot policies.**

Named for Skuld, the Norn of what shall be, whose name also means *debt*: the regression suite every release must pay.

Skuld does not celebrate a robot policy's normal operation. It searches for the smallest world change that breaks the policy in simulation, minimizes that failure to the variables that matter, stores it as a replayable regression test, and blocks any release that fails it.

Built by Team ODIN for the Nebius x NVIDIA Global AI Hackathon, Physical AI track. Everything below that reads as a result was run on this repository's code and is archived under `evidence/`, with SHA-256 manifests. Nothing is simulated-by-hand, illustrated or estimated.

## What it does, as run

1. **Searches.** Two strategies over the same four-variable domain (block offset, mass, friction, observation delay), same oracle, same budget of 25 episodes: uniform random, and an inspectable explore-then-contract search that bisects from the nearest failure toward nominal with adaptive jitter.
2. **Judges.** A deterministic oracle reads only recorded simulator state against a human-approved `TestSpec`. Status machine `PASS | TASK_FAIL | SAFETY_FAIL | INVALID | TIMEOUT | EXEC_ERROR`, fail-closed: anything it cannot judge is `INVALID`, never a pass.
3. **Minimizes.** Greedy revert of each perturbation to nominal, nearest first, then bisection toward nominal on what remains, with a monotonicity probe. Replayed on a seed set.
4. **Stores and gates.** The counterexample becomes a regression test. A release candidate must pass nominal, every stored regression and a reserved held-out set, or it is `BLOCKED`. Missing evidence is `INCOMPLETE`; corrupt or mismatched evidence is `ERROR`. `ELIGIBLE` means "passed the named simulation suite", never "safe".
5. **Grounds.** A live Tavily search fetched the manufacturer's datasheet; a payload constraint extracted from it became usable only after a human approved it, and it fed a hypothesis that was executed and judged.

Governing principle: **generative AI proposes, deterministic engineering decides, humans authorize cost, safety limits and deployment.**

## Results

All numbers from `evidence/G12/g12_report.json` (frozen rerun at the commit named in `evidence/G12/frozen_commit.txt`), `evidence/G10/` and `evidence/G11/`. One run per strategy at a budget of 25; differences of a few episodes are observations, not trends.

**Policy under test, `push-dls-ik-v1`** (classical damped-least-squares IK push controller, labelled as such; no learning):

| Evaluation | Nominal | Random testing | Skuld active search |
|---|---|---|---|
| Episodes used | 3 | 25 | 25 |
| Failures found | 0 | 3 | 6 |
| Episodes to first failure | - | 16 | 6 |
| Closest failure distance (normalized L2 to nominal) | - | 0.885 | 0.781 |
| Reproducible failures | 3/3 nominal byte-identical | 25/25 episodes byte-identical to the G07 archive | 25/25 byte-identical to the G10 archive; minimized failure 3/3 replays identical |
| Compute time (CPU laptop, unrendered 15 s episodes) | 1.4 s | 14.4 s | 12.0 s |

**Minimized counterexample** (`evidence/G10/counterexample.json`): the nearest active failure had all four variables perturbed. Offset, mass and friction were reverted to nominal and the episode still failed. What remains is **an observation delay of 140 ms with everything else nominal**: the fingers touch the floor during descent (`SAFETY_FAIL: NEVER collision`), distance 0.700. Bisection puts the pass bound at 131 ms on that axis. Locally minimized under this simulator and controller; not a global minimum, not a causal claim.

**Release gate** (`evidence/G11/`): same suite, same commit.

| Suite | v1 | v2 (repair: descent capped at 0.05 m/s below 6 cm, push height 3 cm) |
|---|---|---|
| Nominal (3) | 3 PASS | 3 PASS |
| Stored regressions (2) | 2 SAFETY_FAIL | 2 PASS |
| Held-out (5, reserved before any search) | 2 SAFETY_FAIL (delays 151 and 180 ms) | 5 PASS |
| Decision | **BLOCKED** | **ELIGIBLE** |

Nine injected faults (missing case, truncated recording, corrupt artifact, failed job, stale policy hash, wrong spec, tampered verdict, and the real violation) all fail closed.

**Negative result, stated plainly.** The repaired v2 is eligible under the ten-scenario suite and still breakable: the G12 rerun of active search on v2 found 7 failures in 25, the nearest at distance 1.013 (delay 182 ms, friction 0.30), where random found 1 in 25. That failure is the next regression test, which is the point of the loop.

Videos: `evidence/G05/nominal.mp4`, `evidence/G07/first_random_failure.mp4`, `evidence/G10/original_failure.mp4`, `evidence/G10/minimized_failure.mp4`, `evidence/G11/push-dls-ik-v2_on_reg-ce-act-020-minimized.mp4`. All rendered from the simulator camera, 640x480 at 25 fps, each judged by the oracle.

## Integrations, honestly labelled

| Integration | Status | Evidence |
|---|---|---|
| MuJoCo 3.17.0 (CPU, local, WSL2) | EXECUTED, closed-loop control every step | `evidence/G05/`, `G07/`, `G10/`, `G11/`, `G12/` |
| Tavily Search API | EXECUTED, one live runtime call with request id, status, URLs | `evidence/G08/tavily_search.json` |
| Nebius Token Factory / NVIDIA Nemotron | **NOT EXECUTED.** Code paths exist for a typed hypothesis client; no key and no runtime call at submission time. The hypothesis in `evidence/G08/hypothesis.json` is labelled human-authored. | none; see `docs/gates/` |
| Nebius AI Cloud GPU rollouts, Isaac Lab, GR00T, Cosmos | not used (zero-spend decision; no local GPU) | none |

## Scope

| | |
|---|---|
| Robot / task | Franka Emika Panda (MuJoCo Menagerie, Apache-2.0, pinned `f3b6013`), push a 4 cm block into a 4 cm target disk |
| Simulator | MuJoCo 3.17.0, CPU, deterministic, local |
| Policy under test | classical controller, `kind = classical` in its manifest; `latest.pt` is never an identity |
| Perturbations | `object_offset_m` [-0.10, 0.10], `object_mass_kg` [0.05, 0.5], `friction_coefficient` [0.2, 1.0], `observation_delay_ms` [0, 200]; all distance weights 1.0; locked in `skuld/core/protocol.py` before any search |
| Dashboard | four read-only HTML surfaces over `evidence/`: Test Lab, Failure Atlas, Counterexample Replay, Release Gate |

## Running it

Developed and run inside WSL2 Ubuntu 24.04 on a Windows laptop with no GPU. Exact package versions: `requirements.lock.txt` (app), `evidence/G12/requirements.sim.freeze.txt` (simulator venv).

```bash
# app environment: contracts, oracle, gate, dashboard, tests (no simulator)
python -m pip install -e ".[dev]"
ruff check . && python -m pytest -q
uvicorn skuld.api.main:app --host 127.0.0.1 --port 8765   # then open / , /atlas , /counterexample , /release

# simulator environment (separate venv) and the pinned Panda model
bash scripts/g05_setup.sh            # creates ~/.venvs/skuld-mujoco, sparse-clones Menagerie, EGL smoke test
export SKULD_MENAGERIE_DIR=~/src/mujoco_menagerie MUJOCO_GL=egl

# gates, each writes evidence/G##/ (see docs/gates/G##_report.md)
bash scripts/g07_run.sh              # locked protocol, nominal runs, 25-episode random baseline
bash scripts/g10_run.sh              # active search, minimization, replays, two videos
bash scripts/g11_run.sh              # test suite, release decisions for v1 and v2, fault injection
bash scripts/g12_run.sh              # frozen rerun of nominal / random / active for both policies
```

Environment variables (see `.env.example`; real values live only in a git-ignored `.env`):
`TAVILY_API_KEY` (G08 only), `NEBIUS_TOKEN_FACTORY_API_KEY` and `SKULD_NEMOTRON_MODEL_ID` (G04, unused so far), `SKULD_MENAGERIE_DIR`, `MUJOCO_GL`, `SKULD_EVIDENCE_DIR` (dashboard root, defaults to `evidence/`).

Smoke tests: `curl http://127.0.0.1:8765/health`; `bash scripts/dashboard_smoke.sh`; `python -m pytest -q` (80 tests, including 13 release-gate fault cases and a render of all four surfaces over the archived evidence).

## Limitations

- **Simulation only.** Results describe the tested simulation envelope: one scene, one controller, CPU MuJoCo. Nothing here certifies a real robot.
- **Small budgets.** 25 episodes per strategy, one run each. The active-vs-random comparison is one observation, not a statistical claim.
- **One mechanism found.** Every failure observed so far is the same signature: fingers touching the floor under observation delay. The task failure modes of the controller were not exercised.
- **Classical policy.** The controller under test is hand-written; no learned policy was evaluated. GR00T and Isaac Lab were out of reach on this hardware and budget.
- **Nemotron not called.** The hypothesis step was performed by a human and labelled so. The NVIDIA-model and Token Factory runtime requirement is therefore **not met by a runtime artifact in this repository**.
- **Minimization is local.** Greedy revert plus bisection; the monotonicity probe is one extra episode per axis.

## Repository map

- `spec.md` full specification and decision log; `CLAUDE.md` operating rules for the Claude Code companion
- `docs/rules.md`, `docs/scope.md`, `docs/sources.md` hackathon rules, scope lock, source and license register; `docs/gates/` one evidence report per gate; `docs/video_script.md`
- `skuld/` application package: `core` (contracts, domain, locked protocol), `sim` (MuJoCo adapter, episode runner, video), `policies` (v1, v2), `oracle`, `search` (objective, active search, minimizer, plot), `release` (registry, gate), `api` (dashboard), `artifacts` (hashing), `integrations/tavily`
- `web/` Jinja templates and CSS for the four surfaces
- `scripts/` gate runners; `tests/`; `evidence/G##/` archived run artifacts with manifests

## How this is built

Skuld is developed by Team ODIN with Claude Code (Anthropic) as an engineering companion. Claude writes code, docs and tests and runs local checks; humans decide scope, approve specs, constraints and any spend, review every gate and own the submission. Commits Claude contributed to carry a `Co-Authored-By: Claude` trailer, and `CLAUDE.md` records the rules it works under. Nothing is reported as working unless it ran and left evidence under `evidence/`.

## License

Apache-2.0. See `LICENSE`. The Franka Panda model is from MuJoCo Menagerie, Apache-2.0 (`evidence/G05/panda-model-LICENSE.txt`). Other third-party sources and versions: `docs/sources.md`.
