# G01 | Local workstation and toolchain

```yaml
schema_version: skuld.gate-report.v1
gate: G01
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '16a76015c85b101af33a785177b125ac4b6083e2'
environment: 'WSL2 Ubuntu 24.04.5 LTS on Windows 11 Pro host; kernel 6.18.54.1-microsoft-standard-WSL2; Python 3.12.3; 8 vCPU; 7.6 GiB RAM in WSL'
commands:
  - 'wsl --install -d Ubuntu-24.04                                   # human, elevated PowerShell'
  - 'sudo bash /mnt/c/Skuld/scripts/bootstrap_wsl.sh                  # human, apt toolchain'
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/inventory_wsl.sh'
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g01_verify.sh'
  - 'git init -b main; git commit (16a7601)'
evidence_paths:
  - evidence/G01/versions-windows-host.txt
  - evidence/G01/versions-wsl-ubuntu-before-apt.txt
  - evidence/G01/versions-wsl-ubuntu-after-apt.txt
  - evidence/G01/requirements.freeze.txt
  - evidence/G01/ruff.txt
  - evidence/G01/tests.txt
  - evidence/G01/health.json
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q: 1 passed, 1 warning in 0.63s (exit 0)'
  - 'GET http://127.0.0.1:8765/health: HTTP 200, {"status":"ok","service":"skuld","version":"0.0.1","python":"3.12.3","platform":"Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.39"}'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G02: schemas, adapter interface, artifact manifest, tests, pinned lock; push to origin so CI runs.'
```

## Acceptance check (runbook G01)

| Criterion | Result |
|---|---|
| Claude CLI opens | Claude Code 2.1.310 runs on the Windows host and drives WSL2 via `wsl.exe`. Not installed inside Ubuntu; not needed. |
| `python -m pytest` runs a smoke test | 1 passed (EXECUTED 2026-10-26) |
| Docker starts (if chosen) | Not chosen for the MVP; Docker Desktop 29.8.2 exists on the host |
| Git commit exists | `16a7601` |
| `GET /health` returns 200 and UI can retrieve it | 200 from uvicorn inside WSL2; UI arrives in G11 |
| Versions and lockfile recorded | `requirements.freeze.txt` (42 packages). This is a capture, not yet the committed lock; G02 promotes it to `requirements.lock.txt`. |

## Toolchain installed (EXECUTED, from `versions-wsl-ubuntu-after-apt.txt`)

| Tool | Version |
|---|---|
| Ubuntu | 24.04.5 LTS |
| python3 | 3.12.3 (venv + ensurepip ok) |
| pip (in venv) | 26.2.2 |
| git | 2.43.0 |
| gcc / cmake | 13.3.0 / 3.28.3 |
| ffmpeg | 6.1.1 |
| jq | 1.7 |
| curl | 8.5.0 |
| Mesa GL libs | libgl1, libegl1, libosmesa6, libglu1-mesa (for MuJoCo offscreen rendering; untested until G05) |
| Nebius CLI, npa | not installed (G04) |
| node | not installed (not needed; Next.js dropped) |

## Decisions made in this gate

- **Checkout location:** repo stays at `/mnt/c/Skuld` so Windows-side tools and the editor see it. **Virtualenvs live in the Linux filesystem** at `~/.venvs/skuld` (app) and later `~/.venvs/skuld-mujoco` (simulator), per the spec's separate-environment rule. If pytest on `/mnt/c` becomes slow as the test suite grows, move the checkout to `~/skuld` and open it from Windows via `\\wsl$`.
- **Invocation path:** Claude drives WSL from the PowerShell tool with `wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/<name>.sh`. The Git Bash tool rewrites `/mnt/c` paths and is unusable for this.
- **Git identity (repo-local):** author Adam Crozier <adam.r.crozier@gmail.com>; every Claude-assisted commit carries `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Remote: https://github.com/atcro/skuldai (private as of 2026-10-26, HTTP 404 unauthenticated).

## Notes and warnings

- pytest emitted `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Harmless for now. Decide in G02 whether to add `httpx2` to dev deps or filter the warning.
- WSL2 sees 7.6 GiB of the host's 16 GiB. Fine for CPU MuJoCo at small episode budgets; watch memory when running sweeps in parallel.
- Line endings: `.gitattributes` enforces LF in the repo; Git on Windows warned about CRLF in working copies, which is expected.

## Cost and approval

No spend. No provisioning. apt packages only.
