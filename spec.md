# Skuld Specification

**Version:** 0.1 draft for review
**Date:** 2026-10-25
**Derived from:** `docs/source-pdfs/BoundaryLab_ The Physical AI Project I Would Bet the Hackathon On.pdf` (concept / deep-research pitch, 2026-10-24) and `docs/source-pdfs/BoundaryLab_Verified_Engineering_Runbook_Team_ODIN.pdf` (audited engineering runbook, 2026-10-25).
**Project status:** AUDITED BLUEPRINT, NOT AN IMPLEMENTED SYSTEM. No code exists yet. No gate has passed.

> **Naming note (DECIDED 2026-10-25):** the product is **Skuld**; the entity is **Skuld AI**; the team is **Team ODIN**. Both source documents use the earlier working name *BoundaryLab*, which is retired. Skuld is the Norn of what shall be in the Völuspá; her name shares a root with "shall" and means *debt* or *obligation* in Old Norse and modern Scandinavian languages. The regression suite is the debt every release must pay. Odin is the one who seeks the Norns' knowledge of what is to come, so Team ODIN building Skuld is coherent. Known namesakes outside AI/robotics: a Norwegian marine insurance club, a goddess character in the manga *Oh My Goddess!*, minor game characters. Checking domain and GitHub org availability is a G00 task.
>
> **One-line lore for README and video:** "Named for Skuld, the Norn of what shall be, whose name also means debt: the regression suite every release must pay."
>
> **Tagline candidates (pick one in G12):** "Skuld knows how your robot will fail before it does." / "Skuld: what your robot policy owes before it ships." / "Crash-test robot intelligence before reality does."

---

## 0. How to read this document

Every statement carries one of these labels, taken from the runbook's grounding protocol:

| Label | Meaning |
|---|---|
| **DECIDED** | Fixed by the source documents or by the hackathon rules. Changing it needs an explicit team decision. |
| **PROPOSED** | Our own design. Reasonable default, open to review. |
| **DOC-VERIFIED** | A vendor command, flag or URL that was seen in official documentation on 2026-10-25. Not yet run here. |
| **EXECUTED** | Run in our environment with saved evidence. Only the host inventory in §12.1 is EXECUTED so far. |
| **OPEN** | Needs a human decision or account-specific verification before work depends on it. |

Section 17 collects every OPEN item in one place for the review.

---

## 1. Mission

**DECIDED.** Skuld is falsification-driven CI/CD for embodied robot policies: *the crash-test lab for robot intelligence.*

Given a robot policy that passes its nominal benchmark, Skuld:

1. **Finds** a nearby world that breaks it (active adversarial search over bounded physical perturbations).
2. **Minimizes** that failure to the smallest reproducible counterexample it can observe.
3. **Explains** it in physical terms (which variables matter, which do not).
4. **Stores** it as an immutable, replayable regression test (scenario + seed + simulator version + policy hash + trajectory + video).
5. **Gates** every subsequent policy release: nominal suite + all stored counterexamples + held-out cases must pass, or the release is BLOCKED.
6. Optionally **repairs** the policy and proves the fix did not create new failures.

Five-year-old version: car companies crash-test cars before selling them. Skuld crash-tests robot brains before letting them ship.

The product is not the robot. The product is the engineering system that decides whether the robot intelligence is trustworthy enough to release.

---

## 2. Problem, thesis and novelty claim

### 2.1 The falsification formulation (DECIDED)

- Nominal world: `x0`.
- World parameter vector: `x = [friction, mass, pose, camera offset, latency, noise, lighting, ...]` (MVP uses at most 4 variables, see §7.1).
- Policy `π` produces a trajectory `τ(π, x)` in the simulator.
- A requirement `φ` (the specification) has a robustness value `ρ(τ, φ)`: positive = satisfied, negative = violated.
- Skuld solves: **`x* = argmin D(x, x0)` subject to `ρ(τ(π, x), φ) < 0`**. Find the world closest to normal that breaks the robot.
- The **robustness margin** of a policy is `M(π) = min over failing x of D(x, x0)`. A tiny margin means the nominal benchmark gives false confidence.

### 2.2 Core thesis to test, not to assume (DECIDED)

Under the same simulation budget and the same allowed parameter domain, active adversarial search will discover failing configurations and/or closer-to-nominal failures more effectively than uniform random search. **This is a hypothesis.** If it fails, we report that and lean on minimization + reproducibility + release gating as the demonstrated value.

### 2.3 Novelty claim we can defend (DECIDED)

Adversarial robot testing, digital-twin falsification, STL-based requirements and failure-driven policy improvement all exist in the literature. We do **not** claim to have invented adversarial testing.

Claim: *Skuld turns adversarial Physical AI testing into a reproducible, counterexample-minimizing CI/CD system built natively across NVIDIA robot/world models and Nebius Physical AI infrastructure.*

Supporting references (see §18): Causal Falsification of Digital Twins (JMLR 2026); Learning of Robot Safety Policies via Adversarial Synthetic Scenarios (2026); RoboTTT (2026); STL-guided policy learning (2026).

### 2.4 Governing principle (DECIDED)

> **Generative AI proposes. Deterministic engineering decides. Humans authorize cost, safety limits and deployment.**

No LLM output is ever authoritative for pass/fail, safety thresholds, or release eligibility.

---

## 3. Hard external constraints

**DECIDED, from the Devpost rules [S01], live-checked 2026-10-25 by the runbook author. Re-verify in G00.**

| Constraint | Value |
|---|---|
| Event | Nebius x NVIDIA Global AI Hackathon, Physical AI track |
| Submission deadline | **Friday 2026-10-30, 10:00 AM PDT / 1:00 PM EDT** |
| Internal target | Submit **Thursday 2026-10-29**. Oct 30 morning is emergency buffer only. |
| Eligibility: models | At least one NVIDIA open model used (Nemotron via Token Factory satisfies this). |
| Eligibility: runtime | Runtime call to Nebius Token Factory **OR** runs on Nebius AI Cloud compute. Both is desirable, not required. |
| Video | Public YouTube, **under** 3:00. Simulation-only is allowed; at least one minute must visibly show the key application modules operating. No fabricated speed-ups or results. |
| Repository | Public, visible open-source LICENSE, reproducible instructions. |
| Tavily bonus ($3,000) | Requires a functional runtime Tavily API call. Separate from main prize. |
| Prizes | Grand Prize $20,000; Physical AI track prize NVIDIA Jetson Orin Nano; a project can receive an overall award or a track award plus one bonus, not stacked overall prizes. |
| Judging | Viability/fit gate, then four equally weighted dimensions: Technological Implementation, Design, Potential Impact, Quality of the Idea. Organizers say a scripted Physical AI demo is table stakes. |
| Timeline after | Judging December 2026; winners expected ~2027-01-11. |

---

## 4. Scope lock (MVP) and non-goals

### 4.1 MVP scope (DECIDED)

- **One** robot, **one** task, **one** scene, **one** policy under test.
- **One** real observation-to-action closed loop: the controller's action is recomputed from the current observation every control step. A pre-recorded trajectory is never presented as a policy.
- **Maximum 4 perturbation variables** until the baseline works (start with 2).
- An immutable policy release manifest.
- Nominal / random / targeted-search comparison on matched budgets.
- Failure minimization and toleranced replay.
- Dashboard with exactly **four** surfaces: Test Lab, Failure Atlas, Counterexample Replay, Release Gate.
- Live Nemotron call (Token Factory) and live Tavily call, each with evidence.

### 4.2 Task choice (DECIDED 2026-10-25)

**Push a block into a target region** on a tabletop with a **Franka Emika Panda** arm from MuJoCo Menagerie. No grasp. Judges understand it instantly, a reliable Cartesian push controller is a matter of hours, and the failure modes (overshoot, miss, stall under low friction or delayed observations) are visible on video.

Upgrade to pick-and-place only if the push loop, oracle, random baseline and active search are all done with a full day to spare. Never fake success.

### 4.3 Simulator and policy for the MVP (DECIDED)

- **Simulator:** MuJoCo via `pip install mujoco`, CPU, local. Models from MuJoCo Menagerie where license and task fit [S05][S08].
- **Policy under test:** a real feedback controller (classical or small learned). It is labelled honestly in the policy registry as `classical`, `heuristic` or `learned`. It is **never** called GR00T unless G14 proves closed-loop GR00T control.

### 4.4 Priority order (DECIDED)

```
MUST HAVE
 1. real Nebius workload (Token Factory call at minimum)
 2. live simulator (MuJoCo, local)
 3. policy under test
 4. adversarial search
 5. deterministic failure oracle
 6. minimal counterexample
 7. reproducible replay
 8. measured comparison against random testing
 9. real Nemotron call
10. real Tavily call

STRETCH (only after G10 passes)
11. GR00T N1.7 as policy under test
12. targeted fine-tuning / repair
13. Cosmos visual augmentation
14. cross-model (simulator vs world model) disagreement
15. Nebius GPU rollouts via NPA workflow

MOONSHOT (not for this submission)
16. edge runtime risk guard
17. real robot / Jetson
18. multiple embodiments
19. multi-simulator validation
```

### 4.5 Non-goals (DECIDED)

- No factory dashboards, digital twins of plants, five production lines or five robots.
- No "LLM controls the robot" architecture.
- No claim of universal safety, certification or "safe for a real robot". The approved phrase is *"robust within the tested simulation envelope"*.
- No Postgres, Polars, MLflow, LangGraph, React charting or GPU libraries until a feature needs them.
- No MCP integration first; CLI/SDK + files first.

---

## 5. Architecture and authority boundaries

### 5.1 System diagram (DECIDED)

```
                      web dashboard (read-only results, 4 surfaces)
                                      |
                           FastAPI + typed Pydantic schemas
                                      |
                        controlled experiment orchestration
                 /                    |                        \
   Tavily Search/Extract      Nemotron via Nebius          Human review
   (external evidence,        Token Factory                (approves limits,
    UNTRUSTED text)           (hypotheses, typed JSON)      billing, releases)
                 \                    |                        /
                        VALIDATED SCENARIO CONTRACT
                        (allowlisted variables, SI units, bounds)
                                      |
                        adversarial search + job scheduler
                 /                                            \
   CPU/local MuJoCo simulator                 optional: Nebius GPU / NPA workflow /
   (first vertical slice)                     Isaac Lab / GR00T (G09, G13, G14)
                 \                                            /
                        trajectory + raw telemetry (per step)
                                      |
                     DETERMINISTIC SPECIFICATION ORACLE
                                      |
                         fail -> minimize -> replay
                                      |
                     immutable artifacts + regression set
                                      |
            release candidate -> ELIGIBLE / BLOCKED / INCOMPLETE / ERROR
```

### 5.2 Who is allowed to decide what (DECIDED)

| Decision | Authority | Explicitly NOT allowed |
|---|---|---|
| Which experiments to run next (hypotheses) | Nemotron proposes, validated by schema | Nemotron cannot return `{"safe": true}` and have it mean anything |
| Physical constraints / safety limits | Human approves a versioned `TestSpec` | A web page, a Tavily result or an LLM can never change limits directly |
| Pass / fail of an episode | Deterministic oracle over simulator telemetry | Visual judgment from one frame; LLM judgment |
| Release eligibility | Deterministic release gate; fail-closed | Any mock, any LLM, any missing evidence treated as pass |
| Paid cloud actions, storage provisioning, license acceptance | Human only, written approval | Claude Code acting on its own |
| Hardware deployment | Human only, outside this system | "ELIGIBLE" being read as "safe for hardware" |

### 5.3 Cloud control-plane distinctions (DECIDED, from [S02][S03][S04])

- **Nebius Token Factory** = hosted model inference (Nemotron). Not a GPU container runtime.
- **NPA / Physical AI Workbench** = agent-facing control plane for configured workloads and artifacts. Installing `npa` locally grants no quota and creates no SkyPilot/Kubernetes runtime.
- **Serverless Jobs, Serverless Endpoints, DevPods, NPA workflows** are related but distinct paths. Never substitute an invented API for one of them.
- Token Factory + local MuJoCo already satisfies the either-or eligibility rule. Cloud simulation (G09) is optional and high-value, not required.

### 5.4 LLM orchestration vs physical testing (DECIDED)

| | LLM orchestration | Physical testing |
|---|---|---|
| Tool | LangGraph optional, later | NPA workflow / our deterministic scheduler |
| Nature | flexible reasoning | deterministic state transitions, artifact contracts |

---

## 6. Domain model and data contracts

**PROPOSED** (names and fields from the runbook; exact fields are ours to finalize in G02). All schemas are Pydantic v2 with `extra='forbid'`, versioned, SI units only, and each carries a `schema_version`.

### 6.1 Core entities

| Schema | Purpose | Key fields |
|---|---|---|
| `TestSpec` | Human-approved, versioned requirement set for a task | `spec_id`, `version`, `task`, `goal_condition` (target region, stability steps), `deadline_s`, `safety_rules` (collision, workspace limits, force limit only if telemetry exists), `approved_by`, `approved_at`, `sha256` |
| `PerturbationDomain` | Allowlisted variables with bounds, units and distance weights | `variables[]` each `{name, unit, nominal, min, max, weight}`; `distance_fn` id; frozen before search |
| `Scenario` | One concrete world configuration | `scenario_id`, `domain_ref`, `values{}` (must be inside domain), `seed`, `sha256` |
| `Observation` / `Action` | Per-step I/O of the policy | typed arrays with declared dimensions and units; `sim_time_s`; `delay_applied_ms` |
| `Trajectory` | Per-step telemetry at fixed simulator cadence | `steps[]` of state, observation, action, contacts, timestamps; `sim_version`; `scene_sha256` |
| `EpisodeResult` | Oracle verdict for one run | `episode_id`, `scenario_id`, `policy_ref`, `status` (§6.2), `violations[]`, `robustness` (optional, grounded), `distance_from_nominal`, `artifact_uris[]`, `correlation_id` |
| `PolicyManifest` | Immutable policy identity | `policy_id`, `kind` (`classical`/`heuristic`/`learned`), `checkpoint_sha256` or `source_sha256`, `description`, `created_at`. `latest.pt` is never an identity. |
| `Hypothesis` | Nemotron's structured proposal | `hypothesis`, `variables[] {name,min,max}`, `reason_to_test`, `expected_failure_signature`, `model_id`, `request_id`, `evidence_refs[]`. Rejected if any variable is outside the approved domain. |
| `DocumentedConstraint` | A sourced fact from Tavily, pending approval | `property`, `value`, `unit`, `source_url`, `quote_or_paraphrase`, `extraction_confidence`, `authorizer`, `approval_state` (`proposed`/`approved`/`rejected`) |
| `Counterexample` | A minimized, reproduced failure | `original_scenario`, `minimized_scenario`, `removed_variables[]`, `kept_variables[]`, `replay_seed_set[]`, `observed_failure_rate` + interval, `replay_video_uri` |
| `ReleaseCandidate` / `ReleaseDecision` | The CI/CD verdict | `policy_ref`, `sim_version`, `test_suite_ref`, `seed_lists`, `commit_sha`, per-suite results (nominal, regression, held-out), `status` (§6.3), `blocking_reasons[]` |
| `ArtifactManifest` | Integrity record | every file with `sha256`, size, producer, immutable name; raw vs derived separated |
| `GateReport` | Project-owned gate evidence (see §13.2) | YAML in `docs/gates/G##_report.md` |

### 6.2 Episode status machine (DECIDED)

```
RUNNING -> PASS | TASK_FAIL | SAFETY_FAIL | INVALID | TIMEOUT | EXEC_ERROR
```

- `TASK_FAIL` and `SAFETY_FAIL` are distinct. Missing the bin is not a collision hazard.
- `INVALID` covers NaN, missing fields, timebase mismatch, physically impossible values, incomplete artifacts, missing telemetry required by the spec.
- `EXEC_ERROR` is an infrastructure problem, never counted as a policy failure or a policy success.
- Only `TASK_FAIL` and `SAFETY_FAIL` count as *valid failures* for search and minimization.

### 6.3 Release status machine (DECIDED)

```
ELIGIBLE | BLOCKED | INCOMPLETE | ERROR
```

- Any verified violation in a required suite -> `BLOCKED`.
- Any required case not executed, telemetry missing, regression not evaluated -> `INCOMPLETE`.
- Job status unknown, artifact integrity mismatch, checkpoint/test mismatch, corrupt evidence -> `ERROR`.
- Only all-required-passed -> `ELIGIBLE`. *Eligible* means "passed the named simulation suite", never "safe".
- Required suites for eligibility: nominal, saved regressions, independent held-out. All three mandatory.

---

## 7. Core algorithms

### 7.1 Perturbation domain for the MVP (PROPOSED)

`x = [object_offset_m, object_mass_kg, friction_coefficient, observation_delay_ms]`

Rules (DECIDED):
- Only perturb variables the policy actually observes or that actually change dynamics. A camera-yaw perturbation is meaningless for a policy that reads joint state. Audit coupling and add a unit test per variable asserting it changes simulator parameters or policy-observed data.
- `observation_delay_ms` is implemented as an observation history buffer indexed by simulator time, accounting for controller frequency and discretization. Document the semantics.
- Start with 2 effective variables; expand to 4 only after both are proven effective.

### 7.2 Distance to nominal (DECIDED)

`D(x, x0) = sqrt( sum_i w_i * ((x_i - x0_i) / range_i)^2 )`

Weights, ranges and bounds are frozen before search. Changing them after seeing results must be disclosed.

### 7.3 Deterministic specification oracle (DECIDED)

- Task completion is defined from simulator state: object within target radius, stable for N steps, within deadline, no workspace violation.
- Safety is measured only from sensors that exist. No force limit is reported if force telemetry is absent or uncalibrated.
- Thresholds come only from a versioned, approved `TestSpec`. LLM-supplied values cannot override them.
- Optional quantitative robustness score (distance to goal, collision clearance, deadline slack) only when grounded in measured state.
- **Stretch (PROPOSED):** a small temporal-logic DSL for the spec, e.g.

  ```
  ALWAYS      force < FORCE_LIMIT          # only if force telemetry exists
  ALWAYS      distance_to_human > SAFE_DISTANCE
  EVENTUALLY[0,5]  object_grasped
  EVENTUALLY[0,12] object_in_target
  NEVER       collision
  ```

  Semantics and units must be specified before any robustness number is reported.

### 7.4 Search (DECIDED approach, PROPOSED algorithm)

- `Objective(x)`: run the policy on scenario `x`, return `task_fail`, `safety_fail`, `distance_from_nominal`, optional graded violation.
- **Baseline:** uniform random search over the same domain with the same episode budget and fixed RNG; every candidate vector recorded.
- **Active search:** a simple, inspectable bounded adaptive method. Default proposal: SciPy differential evolution or a transparent surrogate/random-proposal scheme. Reproducible by seed.
- Retries and failed jobs are counted separately from the episode budget.
- If no failure appears, widen only the declared domain and restart fair baselines. Never widen silently.

### 7.5 Counterexample minimization (DECIDED)

Greedy revert, then bounded local refinement:

```python
def minimize_failure(initial, nominal, run, repeats=3):
    best = initial.copy()
    for key in sorted(best, key=lambda k: abs(best[k] - nominal[k])):
        candidate = best.copy()
        candidate[key] = nominal[key]
        outcomes = [run(candidate, seed=i) for i in range(repeats)]
        # reproducibility threshold defined BEFORE observing outcomes
        if sum(o.is_valid_failure for o in outcomes) >= repeats:
            best = candidate
    return best  # locally reduced; no claim of global optimum
```

- Then refine numeric values with a bounded local search. Test for non-monotonicity; do not assume binary search works.
- Repeat the minimized candidate on a controlled seed set; report observed failure probability with an interval.
- Persist both original and minimized scenarios with real replay footage.
- Approved wording: *"a locally minimized, reproducible failure under our tested simulator and controller."* Never "global minimum" or "causal proof".

### 7.6 Replay and reproducibility (DECIDED)

- Replay = same scenario, seed, scene hash, policy hash, simulator version, precision info.
- Require **toleranced** replay or statistical reproduction. Parallel/GPU solvers need not be bit-identical; CPU MuJoCo usually is, but we disclose the tolerance either way.
- Replay rate = confirmed failures / valid repeated runs on the designated seed set.

### 7.7 Repair loop (STRETCH, PROPOSED)

Change something concrete and explainable (e.g. delay compensation, feedback gain tuning, or targeted data + fine-tune if the policy is learned). Re-run the complete suites: original counterexample, all regressions, held-out. If there is no improvement, show BLOCKED. No magical green demo.

---

## 8. Experimental protocol and metrics

### 8.1 Protocol (DECIDED)

1. Lock task, base scenario, perturbation domain, distance weights and policy version **before** evaluating any search strategy.
2. Partition seeds: search seeds vs held-out evaluation seeds. Also reserve held-out *parameter configurations*, not only seeds.
3. Run 3 to 10 nominal episodes to confirm the policy is worth testing.
4. First budget, from measured throughput: `N_nominal=5, N_random=25, N_active=25`. Expand only after per-episode time/cost is measured. Report small sample size as a limitation.
5. Define primary metrics before looking at results (§8.2).
6. Store every episode: passes, failures, invalids, retries, resumed jobs. No double counting.
7. Verify evaluator agreement by manually replaying a few random-baseline cases.
8. Where feasible, repeat the whole search with multiple independent seeds and report confidence intervals. Report curves (failures found and min distance vs cumulative episodes), not one flattering point.

### 8.2 Metrics (DECIDED)

| Quantity | Must be recorded | Failure mode to avoid |
|---|---|---|
| Task completion | goal state, deadline, source telemetry | visual judgment from one frame |
| Safety violation | collision/force from real simulator fields | invented force values |
| Efficiency | episodes to first verified failure; wall-clock | comparing unequal budgets |
| Nearest failure | metric definition and actual perturbed values | comparing incompatible units |
| Repeatability | repeats, seed set, failure frequency | one stochastic event called deterministic |
| Improvement | v1 vs v2 on original + held-out | optimizing only the known one-off failure |
| Cost | actual time, GPU class, billed or approved estimate | unverified "free compute" claims |
| Provenance | policy hash, scenario hash, runtime/image digest | `latest.pt` treated as immutable |

### 8.3 README results table (DECIDED: real numbers only)

| Evaluation | Nominal | Random testing | Skuld active search |
|---|---|---|---|
| Episodes used | actual | actual | actual |
| Failures found | actual | actual | actual |
| Episodes to first failure | actual | actual | actual |
| Closest failure distance | actual | actual | actual |
| Reproducible failures | actual | actual | actual |
| Compute time / cost | actual | actual | actual |

And if repair works: before/after on original counterexample, held-out adversarial success, regression suite success, nearest discovered failure. Any illustrative number in the source documents (e.g. "87 vs 21 episodes") is **not** to be published.

---

## 9. Release gate semantics

**DECIDED.**

- Inputs: `ReleaseCandidate` with exact policy, simulator, test-suite, seed lists and commit hash.
- Run mandatory nominal + stored regressions + held-out cases.
- Unexecuted or missing -> `INCOMPLETE`. Any verified violation -> `BLOCKED`. Job failure or corrupt evidence -> `ERROR`. All required passed -> `ELIGIBLE`.
- CI: GitHub Actions runs lint + unit tests on every PR with no secrets and no cloud spend. Cloud/simulator evaluation runs only when a human authorizes it.
- Fault injection (mandatory before G11 passes): deliberate missing log, corrupt artifact, failed cloud job, known safety violation. Each must produce `BLOCKED`, `INCOMPLETE` or `ERROR`. The UI must never show green from mock data.

---

## 10. Integrations

Each integration has a load-bearing reason, an eligibility role, a smoke test that proves it actually ran, and a fallback.

| Integration | Role | Eligibility | Smoke test (not optional) | Epistemic status | Fallback |
|---|---|---|---|---|---|
| **MuJoCo** (CPU, local) | Simulator for MVP | none | `import mujoco`, nominal episode, obviously failing episode, replay within tolerance | DOC-VERIFIED [S05] | push/reach task before grasp |
| **Nebius Token Factory / Nemotron** | Scientific test reasoning: structured hypotheses, constraint extraction. Never motor control. | Satisfies "NVIDIA open model" and "Token Factory runtime call" | `npa workbench token-factory generate` with typed prompt, **nonempty completion** captured to JSONL with model ID. Catalog listing alone is not inference. | DOC-VERIFIED [S03]; default base URL `https://api.tokenfactory.nebius.com/v1/`; `NEBIUS_TOKEN_FACTORY_BASE_URL` is an optional override, not required; `nvidia/Nemotron-3_5-Lightning` is a documented example ID, not guaranteed available | choose another NVIDIA open model in the catalog; if none -> G04 BLOCKED, eligibility at risk |
| **NPA / Physical AI Workbench** | Agent-facing CLI for Token Factory; optional workflow runtime for cloud rollouts | optional | `npa --version`, `npa workbench --help` from pinned checkout; `validate-spec` / `plan-spec` without launches | DOC-VERIFIED [S02][S04]; installs from checkout (`pip install -e npa`), not PyPI; pin the commit | Token Factory + local MuJoCo already satisfies rules |
| **Nebius GPU rollouts (G09)** | Parallel rollouts, rendering, GR00T if needed | satisfies "Nebius AI Cloud" alternative | one approved real run with run ID, artifacts, checksum, teardown and cost record; scale 1 -> 5 -> 20 | OPEN (quota, pricing, region unknown) | describe simulation truthfully as local |
| **Tavily** | Engineering evidence layer: fetch public manufacturer/simulator docs; Nemotron extracts a `DocumentedConstraint`; human approves | $3,000 bonus requires functional runtime call | one live `TavilyClient.search(...)` with timestamp, status, result URLs; one evidence -> approved hypothesis -> executed scenario chain | DOC-VERIFIED [S09] | do not claim bonus eligibility; rest of project continues |
| **GR00T N1.7** (G14) | Real learned VLA as the policy under test | stretch | observation -> model -> action -> simulator closed loop over time; inference-only output does not count | DOC-VERIFIED [S07]; requires GPU we do not have locally | keep classical controller, label honestly |
| **Isaac Lab / Isaac Sim** (G13) | NVIDIA simulator via `IsaacAdapter` | stretch | upstream tutorial runs in the exact GPU env, then one Skuld rollout | DOC-VERIFIED [S06]; pin a tag and its compatibility matrix | preserve MuJoCo MVP; stop-loss half a workday |
| **Cosmos 3** (G15) | World-model disagreement: simulator vs Cosmos predicted futures, investigate where they disagree | stretch | n/a this submission | DOC-VERIFIED [S13]; NVIDIA documents temporal inconsistency and says safety-critical use needs extra validation | future-work slide only; generated video is never an oracle |

**Untrusted-input rule (DECIDED):** every Tavily result and every fetched page is untrusted text. It may never command the coding agent, raise a safety limit, or feed cloud operations. Extraction is constrained to the `DocumentedConstraint` schema and requires human approval before any bound changes.

---

## 11. Dashboard surfaces

**DECIDED: exactly four. Read-only over real run records. Any mock or demo-only screen is labelled as such on screen.**

| Surface | Shows |
|---|---|
| **Test Lab** | policy under test, workers, experiments done / budget, failures so far, nearest counterexample distance, live or latest simulation video, job ledger |
| **Failure Atlas** | 2-D success/failure surface over two selectable perturbation variables with the observed boundary; robustness margin `M(π)` |
| **Counterexample Replay** | original vs minimized scenario, removed vs kept variables, replay seed set, observed failure rate, replay video |
| **Release Gate** | per-suite results (nominal, regressions, held-out), status `ELIGIBLE / BLOCKED / INCOMPLETE / ERROR`, blocking reasons, provenance hashes |

Frontend (DECIDED 2026-10-25): **minimal HTML served by FastAPI** via Jinja templates and a small chart library loaded from a CDN. No Node build step. Next.js is dropped from the plan. Chosen because one shared laptop and five days cannot carry a second toolchain; the Design judging dimension is served by clarity and honest labelling, not by framework.

---

## 12. Repository layout and tooling

**SCAFFOLDED 2026-10-25** (runbook structure, adapted: all Python code sits under one `skuld` package so imports read `skuld.core...`). Monorepo, single Python app environment plus isolated simulator environments. Directories exist; most modules are empty until their gate.

```
Skuld/
  CLAUDE.md               operating rules for Claude Code (companion)
  spec.md                 this document
  README.md               public: what/why/how, real results table, limitations
  LICENSE                 Apache-2.0 (DECIDED); asset licenses recorded in docs/sources.md
  .env.example            placeholders only, never real values
  .gitignore              .env, secrets, venvs, checkpoints, runs/, raw provider output
  pyproject.toml          app deps with lower bounds; pinned lock produced in G02 inside WSL2
  skuld/
    api/                  FastAPI app; GET /health exists; dashboard routes arrive in G11
    core/                 schemas (Pydantic, extra='forbid'), units, hashing, correlation IDs
    sim/                  adapter interface + MuJoCo adapter (+ future IsaacAdapter)
                          interface: reset, observe, act, step, terminate, save_trajectory
    policies/             controllers + policy registry (kind, hash)
    oracle/               TestSpec, episode state machine, violations
    search/               random baseline, active search, minimizer, distance
    artifacts/            manifest, sha256, immutable storage (filesystem/SQLite for MVP)
    release/              release candidate, gate state machine
    integrations/
      token_factory/      Nemotron hypothesis client via npa CLI or HTTP
      tavily/             evidence fetch -> DocumentedConstraint
  web/templates, web/static   Jinja templates + static assets for the 4 surfaces, served by FastAPI
  scripts/                smoke_tavily.py exists; smoke_token_factory.* arrives in G04
  tests/                  test_health.py exists; schema, oracle and fault-injection tests arrive in G02+
  docs/
    rules.md              hackathon rules with a human-confirmation column
    scope.md              scope lock and cut order
    sources.md            source register with epistemic labels and pinned versions
    source-pdfs/          the two BoundaryLab PDFs this spec was derived from
    gates/G00_report.md ... G15_report.md
  evidence/               G##/ command logs, versions, JSONL, checksums (secrets scrubbed)
  .github/workflows/ci.yml   ruff + pytest only; no secrets, no cloud spend
```

Environments (DECIDED: separate, never shared):
- `.venv` app: fastapi, uvicorn[standard], pydantic, httpx, numpy, scipy, pytest, pytest-asyncio, ruff, python-dotenv, tavily-python, openai (for the OpenAI-compatible Token Factory endpoint if used directly).
- `.venv-mujoco`: mujoco, numpy, pytest.
- `../nebius-physical-ai/` cloned adjacent to the repo, its own venv, `pip install -e npa`, commit pinned in `docs/sources.md`.
- Isaac / GR00T: separately pinned GPU environments or containers, never contaminating the core app.

### 12.1 Development host (EXECUTED inventory, 2026-10-25)

| Item | Observed |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| CPU / RAM | Intel i7-1185G7 (4 cores), 16 GB |
| GPU | **None NVIDIA** (`nvidia-smi` not found; integrated Intel graphics) |
| Python | 3.12.10 |
| Node / npm | 24.20.0 / 11.19.0 |
| Docker | Docker Desktop 29.8.2 |
| WSL | WSL2 present, only `docker-desktop` distro; **no Ubuntu distro** |
| Git | 2.55.0.windows.5 |
| ffmpeg | 9.0.2 |
| Missing | `jq`, `uv`, Ubuntu WSL, NVIDIA driver |
| Claude Code | 2.1.310 |

Consequences: Isaac Lab, GR00T and Cosmos cannot run locally. They are cloud-only stretch items. CPU MuJoCo is the only viable local simulator, which matches the runbook's first vertical slice.

**DECIDED 2026-10-25 (§17 #2): all development happens inside a WSL2 Ubuntu 24.04 distro**, which G01 installs. Reason, DOC-VERIFIED: the Workbench README and quickstart support "macOS, Linux, or Windows with WSL2 Ubuntu" with Python 3.11+, and the Nebius CLI installer supports Ubuntu and macOS only. The runbook's Linux commands then apply as written. Windows-side tools (ffmpeg, Docker Desktop, browser for the dashboard) remain usable from WSL2. Files are edited from Windows via `\\wsl$` or VS Code Remote.

---

## 13. Gates

### 13.1 Gate table (DECIDED: structure and acceptance from the runbook; owners OPEN)

Statuses: `PASS | FAIL | BLOCKED | NOT_STARTED`. A gate passes only with a working environment and saved evidence, never because code exists.

```
G00 rules and scope
 |--> G01 local tools --> G02 repo + deterministic app --> G05 MuJoCo loop --> G06 oracle --> G07 baseline
 |--> G03 Nebius account --> G04 Nemotron LIVE  -------> (G09 cloud rollout, optional)        \
 +--> G08 Tavily live --> grounded hypothesis ---------------------------------------------> G10 search/minimize
                                                                                                  |
                                                                                           G11 artifacts + release gate
                                                                                                  |
                                                                                           G12 benchmark + demo + submission
ADVANCED ONLY after G10: G13 Isaac Lab, G14 GR00T, G15 Cosmos / edge risk
```

| Gate | Title | Owner | Acceptance (summary) | Evidence | Fallback |
|---|---|---|---|---|---|
| **G00** | Freeze rules, scope, owners (~1 h) | Human + Claude | `docs/rules.md`, `docs/scope.md`, deadline verified, roles fixed, budget cap recorded, license chosen, Devpost owner confirmed; name Skuld confirmed (done) plus domain and GitHub org availability checked and recorded | dated source register, G00 report | no spend until budget confirmed; if `skuld` handles are taken, use `skuld-ai` or `skuld-odin` and record the choice |
| **G01** | Workstation + toolchain | Human installs, Claude verifies | versions recorded; pytest smoke runs; Docker starts (if chosen); git commit exists; `GET /health` 200 | `evidence/G01/{versions.txt,tests.txt,health.json}` | run FastAPI natively if Docker is a problem |
| **G02** | Contracts, repo, CI | Claude owns, human reviews | CLAUDE.md; monorepo scaffold; Pydantic schemas reject unknown keys and bad ranges; adapter interface; manifest + sha256; ruff + pytest (one pass, one collision fail, one malformed-data rejection); GitHub Actions lint+test | commit SHA, CI URL, test log | SQLite + filesystem artifacts |
| **G03** | Nebius account, permissions, resource boundary | Human | tenant/project/region/role documented; prices and quota observed (redacted); separate Token Factory credential and Cloud IAM identity; budget cap, max concurrent jobs (start 1), teardown procedure | redacted account check, signed budget note | Token Factory + local MuJoCo for eligibility |
| **G04** | Install NPA + genuine Nemotron call | Claude with credential | pinned checkout; `npa --version`; `npa configure --no-provision`; `token-factory status/verify/models`; real `generate` with **nonempty completion** from a listed NVIDIA model; hypothesis JSON validated against allowlist | redacted JSONL, model ID, CLI logs, commit hash | another catalog NVIDIA model; else BLOCKED |
| **G05** | Real MuJoCo simulation + observable control | Keyboard lane (human + Claude) | nominal episode; real failed episode; per-step trajectory; truthful video; 2 effective perturbations with tests; toleranced replay; latency semantics documented | scenario JSON, trajectory, video, versions, policy hash, checksums | push/reach before grasp; never label a replay as a policy |
| **G06** | Deterministic specification oracle | Keyboard lane; off-keyboard human reviews definitions | status machine with fixtures per status; no hallucinated force; infrastructure vs policy failures separated; LLM cannot override thresholds; NaN/missing -> INVALID | oracle unit + sensitivity tests, spec sha256 | - |
| **G07** | Baselines, seeds, experimental design | Keyboard lane; off-keyboard human reviews protocol | locked protocol; seed partition + held-out configs; 3-10 nominal runs; budget from throughput; fixed RNG; all episodes stored; distance weights published; metrics predefined; random baseline run and spot-checked | locked protocol, seed lists, CSV/Parquet + checksums | - |
| **G08** | Tavily real evidence step | Keyboard lane (human + Claude) | live search with timestamp/status/URLs; `DocumentedConstraint` with source + approval; untrusted-text rejection; approval step before bounds change; hypothesis linked to executed scenario | filtered output, provenance links, approval event | no bonus claim |
| **G09** | Cloud GPU workload + NPA workflow (**OFF under the zero-spend decision, §17 #4/#10**) | human approval required to re-open | justified need; approved one-job trial; `validate-spec`/`plan-spec` first; custom runtime writes manifest/trajectory/result; spec copied from pinned schema; one real run with run ID, artifacts, checksum, teardown, cost; scale 1 -> 5 -> 20 | run IDs, logs, manifests, cost record | local MuJoCo, described as local |
| **G10** | Adversarial optimizer + minimizer | Keyboard lane (Claude runs sweeps in background) | `Objective(x)`; inspectable bounded search; matched budgets; every candidate logged; a real failure found; greedy-revert + local refinement minimization; repeated on seed set; both scenarios + replay footage persisted | candidate ledger, comparison plot, replay videos, run manifests | widen declared domain honestly; report no-advantage honestly |
| **G11** | CI/CD release decision + UI | Keyboard lane (human + Claude) | policy registry with hashes and honest `kind`; scenario/test registry; release manifest; status machine fail-closed; nominal + regressions + held-out mandatory; concrete repair attempt (or admit none); 4 dashboard surfaces on real records; fault-injection tests pass | CI URL, release JSON, fault-injection tests, screen recording | - |
| **G12** | Final benchmark, demo, public repo, submission | Keyboard lane; laptop owner signs as submission owner | code frozen; nominal/random/targeted rerun on consistent policy and budget; held-out separated; real results table incl. negatives; >=60 s of genuine working modules in a <3:00 video; only real integrations shown; public repo with LICENSE, README, versions, scripts, asset licenses, env vars, smoke tests, limitations; Devpost + YouTube verified incognito | Devpost URL, YouTube URL, repo URL + commit, signed G12 | - |
| G13 | Isaac Lab / Isaac Sim compatibility matrix | stretch | upstream tutorial on exact GPU env + one Skuld rollout via `IsaacAdapter` | artifact proof | stop-loss half a workday |
| G14 | GR00T checkpoint + embodiment | stretch | real closed loop: sim observations -> GR00T -> actions drive sim over time | artifact proof | keep classical controller |
| G15 | Cosmos / edge risk / disagreement | stretch | research extension only | - | future-work slide |

### 13.2 Gate report format (DECIDED, project-owned, not a Nebius format)

```yaml
schema_version: skuld.gate-report.v1
gate: G05
status: NOT_STARTED        # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<git hash>'
environment: '<host + Python + simulator versions>'
commands: []
evidence_paths: []
provider_run_ids: []
actual_test_results: []
spend_approved: false
approved_by: null
blockers: []
next_action: '<concrete follow-up>'
```

Each report also lists prerequisites, source URLs/versions, actual outputs, cost/approval, and the next gate.

---

## 14. Timeline and stop-losses

### 14.1 Day-by-day (re-cut 2026-10-25 for one shared laptop, two humans, one development window)

The runbook assumed two parallel lanes. We have one keyboard. The plan below is a **single serial lane** in which Claude runs long jobs (search sweeps, test suites, gate reports, docs) in the background while the person at the keyboard reviews. The person not at the keyboard owns review, video script, README text and the adversarial checklist on their own device.

| Day (EDT) | Keyboard lane (human + Claude) | Off-keyboard lane (second human) | Hard artifact by end of day |
|---|---|---|---|
| Sun Oct 25 (evening) | G00 close: rules.md, scope.md, decisions recorded. G01: install WSL2 Ubuntu 24.04, toolchain, `git init`. Apply to Builder Program; claim Devpost code. | Read spec.md; confirm rules on Devpost while logged in; start Nebius account check (G03) | G00 + G01 reports; Builder Program application submitted |
| Mon Oct 26 | G02 scaffold + schemas + tests + CI. G05: Panda scene, push controller, nominal + failed rollout, 2 perturbations, replay. G04 live Nemotron call once a key exists. | G03: account, credit balance, Token Factory key (redacted evidence). Draft README skeleton. | two real simulator videos + live Nemotron JSONL + G02/G05 reports |
| Tue Oct 27 | G06 oracle + fixtures. G07 protocol lock, seeds, 5 nominal + 25 random episodes (Claude runs sweep in background). G08 Tavily evidence chain. | Review oracle definitions and protocol before results are seen. Write video script v1. | random baseline + typed failure artifacts + G06/G07/G08 reports |
| Wed Oct 28 | G10 active search (25 episodes), minimizer, reproduction on seed set. G11 release state machine, fault-injection tests, 4 HTML surfaces on real records. One explicit repair attempt. | Review candidate ledger and replay videos; run the adversarial checklist items 1 to 6. | nearest observed failure + replay + comparison + fail-closed release manifest + dashboard |
| Thu Oct 29 | Freeze code. Rerun nominal/random/active on frozen policy. Held-out run. Record video. README results table. Secret scan, LICENSE, flip repo public. **Submit.** | Adversarial checklist items 7 to 10. Incognito verification of Devpost, YouTube, repo. | valid public Devpost submission + G12 report |
| Fri Oct 30 AM | Emergency corrections only | confirm all links accessible | deadline 1:00 PM EDT |

Realistic risk: this is the runbook's two-person-week compressed into one keyboard. If Tuesday ends without G07, drop the repair attempt and the Failure Atlas surface first; protect G10 minimization and G11 fail-closed gating, which are the demo.

### 14.2 Stop-loss rules (DECIDED)

- GPU/Isaac deployment fails after half a day of documented effort -> continue CPU MuJoCo, keep Token Factory integration.
- Grasp controller unreliable after half a day -> push/reach task. Never fake success.
- Adaptive search shows no advantage -> report honestly; emphasize minimization + reproducibility.
- Repair fails -> show BLOCKED. No magical green.
- A model's terms or access are missing -> do not pretend it ran.
- No additional models before a genuine full loop exists.
- Cloud scale-up: 1 -> 10 -> 25 episodes only after per-episode cost is measured and approved.

---

## 15. Security, reliability, observability

**DECIDED.**

- **Identity:** separate work accounts for Nebius/Tavily/NVIDIA; keys only in private env vars or credential files (mode 0600); never in chat, repo or screenshots; least privilege; MFA; rotate anything exposed. `.env.example` holds placeholders only.
- **Isolation:** no untrusted page can modify constraints; no tool execution driven by raw model output; all model output passes Pydantic validation with `extra='forbid'`.
- **Cloud:** approval before any paid resource; record region, quota, billing; idempotent job IDs; explicit cancel/cleanup; bounded retries and timeouts; verify artifacts before treating a "succeeded" job as scientific success. Note: `npa` image preflight may create probe pods and leave a service account; it is not side-effect-free.
- **Artifacts:** atomic writes, manifest checksums, duplicate detection, immutable names, retention policy, raw vs derived separated.
- **Observability:** one correlation ID flows HTTP request -> hypothesis -> scenario -> run -> trajectory -> oracle result -> UI.
- **Reproducibility:** lock dependency/driver/container versions; log seeds and precision; disclose nondeterminism; capture hardware type.
- **Legal:** verify license and attribution before publishing any dataset, manual, generated media, robot model or weights. Document significant new work if any prior code predates the contest.
- **Mandatory fault-injection suite (before release):** timeout; model/API 401; Token Factory catalog with no NVIDIA model; Tavily 429; corrupt trajectory; missing timestamps; NaN state; run status success but artifact absent; duplicate job ID; stale policy hash; failed checksum; seed mismatch; scenario claims friction support but ignores input. Each must fail closed or explicitly block the affected feature.

---

## 16. Demo and submission deliverables

### 16.1 Three-minute storyboard (DECIDED; only recorded actual runs)

| Time | Screen / module | Narration (one line) |
|---|---|---|
| 0:00-0:15 | Nominal robot success | "It passes ordinary tests. Would you ship it?" |
| 0:15-0:40 | Actual scenario search + job ledger | "We perturb only physically meaningful variables." |
| 0:40-1:05 | Replayed real failure + oracle verdict | "It breaks under a small, concrete change." |
| 1:05-1:30 | Minimization + reduced replay | "We remove irrelevant changes and find a smaller counterexample." |
| 1:30-2:00 | Tavily source -> Nemotron hypothesis -> test contract | "The AI suggests; deterministic physics decides." |
| 2:00-2:25 | Release gate / regression rerun | "A bad release gets blocked; a changed policy must retest." |
| 2:25-2:45 | Baseline comparison + artifact proof | "Here are actual results versus random testing." |
| 2:45-2:58 | Architecture + value | "Skuld: crash-test robot intelligence before reality does." |

Keep it under 3:00, not at 3:00. At least a combined continuous minute of visibly operating modules. The signature scene is the minimizer removing irrelevant perturbations.

### 16.2 Submission checklist (DECIDED)

- Public repo: root LICENSE, README with real results table and limitations, exact versions, scripts, asset licenses, env var list, smoke tests, platform feedback.
- Public YouTube URL, Devpost project description, Physical AI track selected, submitted early.
- Incognito verification of Devpost page, video, repo link and license.
- Final evidence manifest archived; approximate billed/credited usage noted.
- Pre-submission adversarial review (listed in CLAUDE.md) with all blocking findings remediated.

---

## 17. Open questions for review

**Status 2026-10-25 evening: all twelve reviewed with the team. Eleven are DECIDED; #8 (Nebius account state) is a fact-finding task for G03, not a decision.** Rows are kept with strikethrough so the reasoning stays visible.

| # | Question | Default if no answer |
|---|---|---|
| 1 | ~~**Name:** ReadyLab, BoundaryLab or Skuld?~~ **DECIDED 2026-10-25: Skuld / Skuld AI.** Remaining sub-task: check domain and GitHub org availability in G00. | closed |
| 2 | ~~**Dev environment**~~ **DECIDED 2026-10-25: everything in WSL2 Ubuntu 24.04.** DOC-VERIFIED: Workbench README/quickstart support "macOS, Linux, or Windows with WSL2 Ubuntu", Python 3.11+; Nebius CLI installer supports Ubuntu and macOS only. Native Windows is viable for app + MuJoCo (EXECUTED: `mujoco-3.17.0-cp312-win_amd64` and `tavily_python-0.8.5` wheels download fine) but splitting stacks adds glue. Docker rejected for now: adds setup and headless-GL work without solving anything the CLIs need; a Dockerfile may be added at G12 for reproducibility. G01 task: install Ubuntu 24.04 under WSL2, then follow the runbook's Linux commands. | closed |
| 3 | ~~**Team**~~ **DECIDED 2026-10-25: two humans + Claude, one shared laptop, one development window at a time.** Consequence: the runbook's two parallel lanes (A simulation, B platform) run **serially** on one machine; the §14.1 day plan must be re-cut as a single lane with Claude doing background work (search runs, test suites, docs, gate reports) while the human at the keyboard reviews. Whoever is not at the keyboard owns review, video script, README and the adversarial checklist. Submission and budget owner: see #4. | closed |
| 4 | ~~**Budget / owners**~~ **DECIDED 2026-10-25.** Devpost submission owner and budget owner are the same person: the laptop owner (the user in this session). **Spend ceiling: zero paid spend** beyond hackathon credits until the credit balance is observed in G03. Allowed: Token Factory calls only if covered by credits. Not allowed without a written re-decision: GPU jobs, object storage, DevPods, Serverless Jobs. G09 is OFF under this ceiling. Max concurrent jobs: 1. | closed |
| 5 | ~~**License**~~ **DECIDED 2026-10-25: Apache-2.0.** Verify compatibility with the chosen Menagerie model's license in G05 and record in `docs/sources.md`. | closed |
| 6 | ~~**Task**~~ **DECIDED 2026-10-25: push a block into a target region.** No grasp. Upgrade to pick-and-place only if the push loop, oracle and baseline are all done with a day to spare. | closed |
| 7 | ~~**Robot model**~~ **DECIDED 2026-10-25: Franka Emika Panda from MuJoCo Menagerie.** Check the model directory's LICENSE in G05 and record it in `docs/sources.md`. | closed |
| 8 | **Nebius account state: UNKNOWN as of 2026-10-25; user is "not sure".** G03 (human-only) must establish it. **Free-credit routes found 2026-10-25:** (a) **Hackathon activation code** reported on the Devpost resources page: `NEBIUS-DEVPOST-GLOBAL26`, claimed via a form, for USD $25 Token Factory credits. UNVERIFIED by Claude (Devpost returns 403 to fetchers); the user must confirm on the resources page while logged in. (b) **Nebius Builder Program** (dev.nebius.com/builders), DOC-VERIFIED from Nebius's own terms: free to join, USD $25 Token Factory credits + USD $25 Tavily credits per verified email, credits expire 90 days after issuance, educational/corporate email preferred, one account per email. The terms grant **no AI Cloud / GPU credit**, so G09 stays OFF. (c) **Nebius for Startups** ($5,000 AI Cloud) requires a venture-backed company; not applicable. **Caution, DOC-VERIFIED:** applying a promo code in the AI Cloud console requires payment details, and adding a card triggers a USD $25 charge credited to the balance. Under the zero-spend decision (#4), do **not** add a card to AI Cloud; use Token Factory credits only. | G03 action: apply to Builder Program with the .edu address today (credits take effect after email verification); confirm the Devpost code; record observed balances redacted in `evidence/G03/` |
| 9 | ~~**Tavily key**~~ **DECIDED 2026-10-25: key is in hand.** Set as `TAVILY_API_KEY` in a private env file in WSL2, never in the repo. G08 is unblocked. | closed |
| 10 | ~~**Cloud rollouts (G09)**~~ **DECIDED 2026-10-25 by consequence of #4: OFF.** Zero paid spend means no GPU jobs. Eligibility is met by Token Factory + local MuJoCo. Revisit only if G03 shows credits that cover it and the budget owner re-decides in writing. | closed |
| 11 | ~~**Public repo timing**~~ **DECIDED 2026-10-25: private until G12, then public** after a secret scan and license check on Oct 29. | closed |
| 12 | ~~**Frontend**~~ **DECIDED 2026-10-25: minimal HTML served by FastAPI** (Jinja templates + a small chart library, no Node build). Next.js dropped from the plan. | closed |

---

## 18. Source register (live-checked 2026-10-25 by the runbook author; pin SHAs on clone)

| Ref | Resource |
|---|---|
| S01 | Devpost rules: https://nebiusglobalaihackathon.devpost.com/rules (also /updates/46204 judging, /updates/46205 how to win) |
| S02 | Nebius Physical AI Workbench README + quickstart: https://github.com/nebius/nebius-physical-ai ; docs/quickstart.md |
| S03 | Token Factory CLI docs: https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory.md |
| S04 | NPA workflow guide + CLI: docs/workbench/npa-workflow-guide.md ; docs/cli/workflow.md |
| S05 | MuJoCo Python bindings: https://mujoco.readthedocs.io/en/stable/python.html |
| S06 | Isaac Lab: https://github.com/isaac-sim/IsaacLab |
| S07 | Isaac GR00T N1.7: https://github.com/NVIDIA/Isaac-GR00T ; scripts/deployment/README.md |
| S08 | MuJoCo Menagerie: https://github.com/google-deepmind/mujoco_menagerie |
| S09 | Tavily: https://docs.tavily.com/documentation/api-reference/endpoint/search ; https://github.com/tavily-ai/tavily-python |
| S10 | Docker Engine install (Ubuntu): https://docs.docker.com/engine/install/ubuntu/ |
| S11 | Claude Code quickstart: https://code.claude.com/docs/en/quickstart |
| S12 | Claude Code permissions: https://code.claude.com/docs/en/permissions |
| S13 | NVIDIA Cosmos: https://github.com/NVIDIA/cosmos |
| R1 | Causal Falsification of Digital Twins, JMLR 2026: https://www.jmlr.org/beta/papers/v27/24-1752.html |
| R2 | Learning of Robot Safety Policies via Adversarial Synthetic Scenarios: https://arxiv.org/abs/2606.05952 |
| R3 | RoboTTT: Context Scaling for Robot Policies: https://arxiv.org/abs/2607.15275 |
| R4 | STL-Guided Stein Variational Policy Gradient: https://arxiv.org/abs/2609.31606 |
| C1 | Nebius Physical AI Living Lab announcement: https://nebius.com/newsroom/nebius-launches-physical-ai-living-lab-for-uk-and-european-robotics-startups-built-with-nvidia-technologies |
| C2 | NVIDIA role postings cited in the pitch (Principal Engineer AV & Physical AI; Director Engineering AV; Sr SWE Low Latency Sensor Systems; Director PM Agent Tooling) via nvidia.wd5.myworkdayjobs.com |
