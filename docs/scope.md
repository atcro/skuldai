# Scope lock

**Frozen:** 2026-10-25 (G00). Changes require a written note here with date and reason.
Full specification: `../spec.md`. Decisions log: `../spec.md` section 17.

## One sentence

Skuld finds the smallest world change that breaks a robot policy in simulation, minimizes it, stores it as a replayable regression test, and blocks releases that fail it.

## In scope (MVP, gates G00 to G12)

| Item | Locked value |
|---|---|
| Robot | Franka Emika Panda, MuJoCo Menagerie model (license to be recorded in G05) |
| Task | Push a block into a target region on a tabletop |
| Scene | One tabletop scene |
| Policy under test | One real feedback controller, action recomputed from the current observation each control step. Labelled `classical` or `heuristic` honestly. |
| Simulator | MuJoCo, CPU, local, inside WSL2 Ubuntu 24.04 |
| Perturbation variables | Start with 2 that provably affect dynamics or observations; maximum 4. Candidates: object offset (m), object mass (kg), friction coefficient, observation delay (ms). |
| Oracle | Deterministic, from simulator state only, thresholds from an approved versioned TestSpec |
| Search | Uniform random baseline and one inspectable bounded adaptive search, matched budgets |
| Minimizer | Greedy revert to nominal plus bounded local refinement, repeated on a seed set |
| Replay | Toleranced replay with seed, scene hash, policy hash, simulator version |
| Release gate | ELIGIBLE / BLOCKED / INCOMPLETE / ERROR, fail-closed; nominal + regressions + held-out mandatory |
| Integrations | Nemotron via Nebius Token Factory (hypotheses, typed JSON); Tavily (evidence, human-approved constraints) |
| Dashboard | Exactly four read-only surfaces: Test Lab, Failure Atlas, Counterexample Replay, Release Gate. Plain HTML via FastAPI + Jinja. |
| First experiment budget | 5 nominal, 25 random, 25 active episodes, expanded only after throughput is measured |
| Repo | Apache-2.0, private until G12, then public after secret scan |
| Budget | Zero paid spend. Token Factory calls only if covered by credits. |

## Explicitly out of scope for this submission

- Cloud GPU rollouts (G09): OFF under the zero-spend decision.
- GR00T, Isaac Lab, Isaac Sim, Cosmos (G13 to G15): stretch, only after G10 passes, and not possible on this laptop.
- Pick-and-place or any grasping task, unless the full push loop is done with a day to spare.
- Repair loop: attempted once on Oct 28 only if G10 is complete; otherwise dropped and reported honestly.
- Temporal-logic specification DSL: stretch.
- Next.js or any Node build step.
- Postgres, Polars, MLflow, LangGraph, MCP.
- Multiple robots, scenes, simulators or embodiments.
- Any claim of real-world safety or certification.

## If time runs short, cut in this order

1. Repair attempt
2. Failure Atlas surface (keep the other three)
3. Tavily evidence chain (lose the bonus, keep eligibility)
4. Active search advantage claim (report honestly; keep minimization + replay + gate)

Protect at all costs: minimized reproducible counterexample, replay, fail-closed release gate, one live Nemotron call with evidence.

## Change log

- 2026-10-25: initial freeze after the twelve-question review.
