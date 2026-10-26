# G02 | Contracts, repository, CI harness

```yaml
schema_version: skuld.gate-report.v1
gate: G02
status: NOT_STARTED    # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<pending>'
environment: '<pending: WSL2 Ubuntu 24.04 + Python version>'
commands: []
evidence_paths: []
provider_run_ids: []
actual_test_results: []
spend_approved: false
approved_by: null
blockers:
  - 'Depends on G01 (WSL2 environment) to run tests with evidence.'
next_action: 'Once WSL2 exists: implement skuld/core/schemas.py (Pydantic v2, extra=forbid, SI units), sim adapter interface, artifact manifest + sha256, tests (one pass, one collision fail, one malformed-data rejection), confirm CI passes.'
```

## Scaffold created on 2026-10-25 (host side, not yet executed in WSL2)

- `CLAUDE.md` with the hard rules (runbook step 23).
- Package tree `skuld/{api,core,sim,policies,oracle,search,artifacts,release,integrations/{token_factory,tavily}}`, plus `web/`, `scripts/`, `tests/`, `docs/`, `evidence/`, `.github/workflows/` (step 24, adapted: Python code lives under a single `skuld` package so imports are `skuld.core...`).
- `pyproject.toml` with app and dev dependencies (lower bounds only; pinned lock to be produced after first resolution in WSL2).
- `skuld/api/main.py` with `GET /health`.
- `tests/test_health.py`.
- `.github/workflows/ci.yml`: ruff + pytest on push and PR, no secrets, no cloud.
- `LICENSE` (Apache-2.0), `README.md` skeleton, `.gitignore`, `.env.example`.

## Still to do for G02 acceptance

- Schemas: `TestSpec`, `PerturbationDomain`, `Scenario`, `Observation`, `Action`, `Trajectory`, `EpisodeResult`, `PolicyManifest`, `Hypothesis`, `DocumentedConstraint`, `Counterexample`, `ReleaseCandidate`, `ReleaseDecision`, `ArtifactManifest` (steps 25 and 26).
- Simulation adapter interface `reset / observe / act / step / terminate / save_trajectory` with explicit errors on unsupported perturbations (step 27).
- Artifact manifest and SHA-256 (step 28).
- Tests: schema rejects unknown keys and out-of-range values; oracle fixtures; one collision failure (step 29).
- CI run URL once the repo is pushed (step 30). The remote stays private until G12.
