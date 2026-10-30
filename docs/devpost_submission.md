# Devpost submission text (draft 2026-10-29, paste into the project page)

Every number below is read from an archived artifact under `evidence/`; file names are
given so a judge can check. Wording follows CLAUDE.md rule 11: no "certified", "safe",
"proven", "global minimum", "causal" or "learned" for this controller.

---

**Project name:** Skuld

**Tagline:** Falsification-driven CI/CD for robot policies: find the smallest world change that breaks a policy, minimize it, store it as a regression test, block the release until it is paid.

**Track:** Physical AI

**Team:** Team ODIN (Skuld AI)

**Repository:** https://github.com/atcro/skuldai (Apache-2.0)

**Video:** <YouTube URL>

---

## Inspiration

Robot policies ship after passing their nominal tests, then fail on small, boring changes in the world: a slightly heavier object, a slicker surface, a sensor reading that arrives a few frames late. Nobody can test every combination. Random domain randomization finds failures late and hands you a four-variable blob nobody can reproduce, and nothing in the pipeline stops the release. Software fixed this decades ago with fuzzing, test-case minimization and CI gates. Robotics mostly has not. Skuld is named for the Norn of what shall be; the name also means debt. Every release owes the regression suite.

## What it does

Skuld takes a robot policy, a simulated task and a locked set of perturbation variables, and runs a loop:

1. **Search** for the smallest world change that makes the policy violate a rule, with a fixed episode budget.
2. **Judge** every episode with a deterministic oracle that reads simulator state against a human-approved spec. No model output anywhere in the pass/fail path.
3. **Minimize** the failure: revert each perturbed variable to nominal, keep only what the failure needs, bisect toward the boundary.
4. **Store** the result as a replayable regression test: scenario, seed, simulator version, policy hash, trajectory, video.
5. **Gate** releases: a candidate is ELIGIBLE only if nominal, stored-regression and held-out suites all pass. Anything missing, stale, corrupt or unknown fails closed.

Generative AI proposes, deterministic engineering decides, humans authorize. Tavily finds the manufacturer's limits, Nemotron proposes hypotheses and extracts constraints, a human approves, physics and the oracle decide.

## What we found (all in simulation, one run per strategy, budget 25)

Task: a Franka Emika Panda pushes a block into a target in CPU MuJoCo. Policy under test: a hand-written classical push controller, labelled as such. Four perturbations: object offset, object mass, friction, observation delay.

- **Nominal:** 3 of 3 PASS, byte-identical across reruns.
- **Random testing:** 3 failures in 25, first at episode 16, nearest at normalized distance 0.885 (`evidence/G07/metrics.json`).
- **Skuld active search, same domain and budget:** 6 failures in 25, first at episode 6, nearest at 0.781 (`evidence/G10/comparison.json`).
- **Minimized counterexample:** offset, mass and friction reverted to nominal and the episode still fails. One variable remains: 140 ms of observation delay. Fingers touch the floor during descent. Pass bound on that axis 131 ms. Three replays, identical step hashes (`evidence/G10/counterexample.json`).
- **Release gate:** v1 BLOCKED on its own two stored regressions and two of five held-out cases (delays 151 and 180 ms). A repaired v2 (slower descent near the table, higher push height) passes all ten. Nine injected faults, from a truncated recording to a verdict edited to PASS, all fail closed (`evidence/G11/`).
- **Negative result, stated plainly:** v2 is eligible under the suite and still breakable. The next search round found 7 failures in 25, the nearest at 182 ms delay with friction 0.30 (`evidence/G12/g12_report.json`). That failure is the next regression test. That is the point of the loop.
- **Frozen rerun:** the final code reproduces the random and active runs 25 of 25 each, byte for byte.

## How we built it

- **Simulator:** MuJoCo 3.17 on CPU, Menagerie Panda model, pinned commit, deterministic. The policy acts every control step at 50 Hz; perturbations are written into the compiled model, the initial state or the observation buffer, each covered by a test.
- **Contracts:** every artifact is a Pydantic schema with unknown keys forbidden. A classical policy cannot be labelled GR00T; a PASS cannot carry a violation; an approved constraint must name its approver.
- **Nebius Token Factory + NVIDIA Nemotron:** two `npa workbench token-factory generate` calls to `nvidia/Nemotron-3_5-Lightning` through the pinned Nebius Physical AI CLI. The model extracted the Panda's rated payload from search snippets and proposed a falsification hypothesis inside the approved bounds. Its first extraction paraphrased the quote and was rejected by a verbatim check; the rejected output is archived unpatched. The accepted hypothesis ran in the simulator and failed the collision rule (`evidence/G04/`).
- **Tavily:** one live search for the manufacturer's payload specification, request id recorded, snippets treated as data. The 3 kg constraint entered the system only after a human approved it (`evidence/G08/`).
- **Dashboard:** four read-only HTML pages over the evidence folder: Test Lab, Failure Atlas, Counterexample Replay, Release Gate.
- **Process:** gates G00 to G12, each with a report and an evidence folder; a pre-submission adversarial review of ten questions; 69 tests in CI. Built with Claude Code as the engineering companion under a written rule set: no invented APIs, no fake numbers, no gate passes because code exists.

## Challenges

A Windows laptop with no NVIDIA GPU and a zero-spend budget. That ruled out Isaac Lab, GR00T and cloud rollouts and put everything on CPU MuJoCo inside WSL2. Keeping the comparison fair took discipline: the random baseline was archived before the search existed, and the runners refuse to start if the protocol, policy or scene hash has changed. The hardest part was saying no: one robot, one task, one scene, four variables, and no new models until the full loop existed.

## What we learned

The validator earned its keep on the first live model call. The deterministic parts of the system, the oracle, the hashes, the fail-closed gate, are what make the AI parts usable. And a repair that passes the suite is not the end: the next search round found the next failure within minutes.

## What's next

- Put a learned policy under the gate. The adapter boundary takes any policy that maps observations to actions each step; a GR00T checkpoint on a GPU box is the obvious next candidate, and the stored regression tests apply unchanged.
- Isaac Lab as a second simulator behind the same adapter; Cosmos as a disagreement signal between predicted and simulated futures.
- Larger budgets and repeated runs so the active-versus-random comparison becomes a statistical claim rather than one observation.
- Claude Code skills that wrap the loop: falsify, minimize, pay-debt, replay, review.

## Limitations, in our own words

Simulation only. One scene, one classical controller, budgets of 25, one run per strategy. One failure mechanism observed. Minimization is local. Results describe robustness within the tested simulation envelope and nothing beyond it.

## Built with

Python, MuJoCo, MuJoCo Menagerie, Pydantic, FastAPI, Jinja, NumPy, Nebius Token Factory, Nebius Physical AI CLI (npa), NVIDIA Nemotron, Tavily, GitHub Actions, WSL2, Claude Code.
