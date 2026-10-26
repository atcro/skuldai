# Skuld

**Falsification-driven CI/CD for embodied robot policies.**

Named for Skuld, the Norn of what shall be, whose name also means *debt*: the regression suite every release must pay.

> **Status: blueprint and scaffold only.** No simulation has run, no gate has passed, no result exists. Nothing in this README is a measured claim until the results table below is filled from archived run artifacts. See `docs/gates/` for the current gate.

## What Skuld does

A robot policy that passes its nominal benchmark may still fail when the camera is displaced slightly or observations arrive late. Skuld does not celebrate normal operation. It:

1. **Searches** for the world closest to nominal that breaks the policy, over bounded, physically meaningful perturbations.
2. **Minimizes** the failing scenario to a locally minimal, reproducible counterexample.
3. **Stores** it, with seed, scene hash, policy hash and simulator version, as a permanent regression test with replay video.
4. **Gates** every subsequent release: nominal suite, every stored counterexample and held-out cases must pass, or the release is `BLOCKED`.

Governing principle: **generative AI proposes, deterministic engineering decides, humans authorize cost, safety limits and deployment.** No model output is ever authoritative for pass/fail.

## Scope of this submission

| | |
|---|---|
| Robot / task | Franka Emika Panda (MuJoCo Menagerie), push a block into a target region |
| Simulator | MuJoCo, CPU, local |
| Policy under test | a classical feedback controller, labelled as such |
| Hypothesis generation | NVIDIA Nemotron via Nebius Token Factory, typed JSON, schema-validated |
| Evidence layer | Tavily search, human-approved constraints only |
| Release gate | `ELIGIBLE` / `BLOCKED` / `INCOMPLETE` / `ERROR`, fail-closed |

Built for the Nebius x NVIDIA Global AI Hackathon, Physical AI track. "Eligible" means "passed the named simulation suite", never "safe for a real robot".

## Results

Not yet measured. This table is filled only from artifacts under `evidence/` and `runs/`.

| Evaluation | Nominal | Random testing | Skuld active search |
|---|---|---|---|
| Episodes used | - | - | - |
| Failures found | - | - | - |
| Episodes to first failure | - | - | - |
| Closest failure distance | - | - | - |
| Reproducible failures | - | - | - |
| Compute time | - | - | - |

## Running it

Instructions arrive with G01 and G02 once they are executed inside WSL2 Ubuntu 24.04. Until then:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
uvicorn skuld.api.main:app --reload
# GET http://127.0.0.1:8000/health
```

## Repository map

- `spec.md` full specification and decision log
- `CLAUDE.md` operating rules for the Claude Code companion
- `docs/rules.md`, `docs/scope.md`, `docs/sources.md` hackathon rules, scope lock, source register
- `docs/gates/` one evidence report per gate
- `skuld/` application package: `api`, `core`, `sim`, `policies`, `oracle`, `search`, `artifacts`, `release`, `integrations`
- `web/` plain HTML dashboard templates (four surfaces)
- `tests/`, `scripts/`, `evidence/`

## Limitations

To be written honestly at G12 from what actually ran. Known in advance: simulation-only, one robot, one task, CPU physics, small episode budgets.

## How this is built

Skuld is developed by Team ODIN with Claude Code (Anthropic) as an engineering companion. Claude writes code, docs and tests and runs local checks; humans decide scope, approve any spend, review every gate and own the submission. Every commit Claude contributed to carries a `Co-Authored-By: Claude` trailer, and `CLAUDE.md` records the rules it works under. Nothing is reported as working unless it ran and left evidence under `evidence/`.

## License

Apache-2.0. See `LICENSE`. Third-party asset licenses (robot model, simulator) are recorded in `docs/sources.md`.
