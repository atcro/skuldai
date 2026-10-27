# G02 | Contracts, repository, CI harness

```yaml
schema_version: skuld.gate-report.v1
gate: G02
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, Python 3.12.3, venv ~/.venvs/skuld, pydantic 2.x per requirements.lock.txt'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g02_verify.sh'
evidence_paths:
  - evidence/G02/ruff.txt
  - evidence/G02/tests.txt
  - evidence/G02/requirements.lock.txt
  - requirements.lock.txt
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra: 35 passed in 0.81s, 0 warnings (exit 0)'
spend_approved: false
approved_by: null
blockers: []
next_action: 'Human records the GitHub Actions run URL for this push below; if it is red, flip this gate to FAIL and fix. Then G05: MuJoCo scene, Panda, push controller.'
```

## Acceptance check (runbook G02, steps 23 to 30)

| Step | Requirement | Result |
|---|---|---|
| 23 | CLAUDE.md with the hard rules | present since G00; status line refreshed in this gate |
| 24 | Monorepo layout | `skuld/{api,core,sim,policies,oracle,search,artifacts,release,integrations}`, `web/`, `tests/`, `docs/`, `evidence/`, `.github/workflows/` |
| 25 | Schemas with `extra='forbid'` | `skuld/core/schemas.py`: TestSpec, PerturbationDomain, Scenario, Observation, Action, Trajectory, EpisodeResult, PolicyManifest, Hypothesis, DocumentedConstraint, Counterexample, ReleaseCandidate, ReleaseDecision, ArtifactManifest, plus enums and supporting models |
| 26 | SI units and ranges, versioned | every `VariableSpec` carries `unit`, `min`, `max`, `nominal`, `weight`; persisted models carry `schema_version = skuld.schemas.v1`; non-finite floats rejected everywhere |
| 27 | Adapter interface with explicit errors on unsupported perturbations | `skuld/sim/adapter.py`: `SimulatorAdapter` with `reset / observe / act / step / terminate / save_trajectory`; `UnsupportedPerturbationError` raised by `check_scenario` |
| 28 | Artifact manifest + SHA-256 | `skuld/artifacts/hashing.py` (`sha256_bytes`, `sha256_file`, `sha256_model`, `entry_for_file`, `verify_entry`) and `ArtifactManifest` / `ArtifactEntry` |
| 29 | Tests: one passing case, one collision failure, malformed-data rejection | `tests/test_schemas.py` (`test_passing_episode_validates`, `test_collision_failure_validates_as_safety_fail`, `test_pass_with_a_collision_is_rejected`, NaN / backwards-time / dimension-change / unknown-key rejections), `tests/test_adapter.py`, `tests/test_hashing.py`, `tests/test_health.py`; 35 tests total |
| 30 | GitHub Actions lint + tests, no secrets, no spend | `.github/workflows/ci.yml` present since G01; first run on the G02 push. **Run URL: _pending human confirmation_** |

## Contract-level guarantees now enforced by the schemas alone

These hold before any oracle or gate code exists, so later code cannot accidentally relax them:

- Unknown keys are rejected on every model. A Nemotron payload containing `"safe": true` fails validation (`test_llm_cannot_smuggle_a_safety_verdict_into_a_hypothesis`).
- A `PerturbationDomain` holds at most 4 variables (scope lock, spec 4.1).
- A `Scenario` can be checked against its domain for completeness and bounds; a `Hypothesis` can be checked against the approved allowlist and bounds.
- `SafetyRules` refuses a force limit unless force telemetry is declared available (spec 7.3).
- `EpisodeResult` refuses `PASS` with violations, `TASK_FAIL` that hides a safety violation, and `RUNNING` as a result (spec 6.2).
- `PolicyManifest` refuses the words GR00T/groot on any non-learned policy and requires an identity hash (CLAUDE.md rule 8, spec 6.1).
- `DocumentedConstraint` cannot be approved without an authorizer and timestamp (spec 10).
- `ReleaseDecision` refuses `ELIGIBLE` unless nominal, regression and held-out suites are all evaluated and all green, and refuses any non-eligible status without a reason (spec 6.3, fail-closed).
- `Counterexample.check_minimized` refuses a "minimized" scenario farther from nominal than the original (spec 7.5).
- `Trajectory` requires contiguous steps, non-decreasing time and constant state dimensions.
- Canonical JSON hashing (`digest()`) is key-order independent.

## Design notes

- All code lives under one `skuld` package (imports `skuld.core.schemas`), a small deviation from the runbook's top-level directories, recorded in spec.md section 12.
- The base-class hash method is named `digest()` rather than `sha256()` so that `ArtifactEntry` can carry a `sha256` field without shadowing.
- Oracle logic (G06), search and minimization (G10) and gate derivation (G11) are not here; the schemas only refuse inconsistent outputs from them.
- `requirements.lock.txt` is `pip freeze --exclude-editable` from the WSL2 venv. CI still resolves from `pyproject.toml`; switching CI to the lock is a one-line change if drift ever appears.

## Cost and approval

No spend. No provisioning. No network beyond PyPI.
