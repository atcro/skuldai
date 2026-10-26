# G01 | Local workstation and toolchain

```yaml
schema_version: skuld.gate-report.v1
gate: G01
status: BLOCKED        # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<pending>'
environment: 'Windows 11 Pro host inventoried; WSL2 Ubuntu 24.04 not yet installed'
commands:
  - 'python --version; git --version; node --version; docker --version; wsl.exe -l -v; ffmpeg -version'
  - 'python -m pip download mujoco --only-binary=:all: --platform win_amd64 --python-version 3.12 --no-deps'
evidence_paths:
  - evidence/G01/versions-windows-host.txt
provider_run_ids: []
actual_test_results: []
spend_approved: false
approved_by: null
blockers:
  - 'WSL2 Ubuntu 24.04 distro not installed. Requires an elevated PowerShell on the host and possibly a reboot. Human action.'
next_action: |
  Human runs in an elevated PowerShell on the host (DOC-VERIFIED shape; confirm the distro name with `wsl --list --online`):
      wsl --install -d Ubuntu-24.04
  Then inside Ubuntu, Claude verifies and records: uname -a, python3 --version, git --version, ffmpeg -version,
  installs build tools per the runbook G01 step 11, creates .venv, installs the app in editable mode,
  runs `python -m pytest`, starts the API and captures GET /health into evidence/G01/health.json.
```

## Acceptance (from the runbook)

- Claude CLI opens inside WSL2.
- `python -m pytest` executes the smoke test.
- Git commit exists.
- `GET /health` returns 200 and is captured to `evidence/G01/health.json`.
- Versions and lockfile recorded, not just install commands.

## Done so far

- Windows host inventoried (EXECUTED). See evidence file.
- Repo tree and `git init` done on the host; the working tree is shared with WSL2 via `/mnt/c/Skuld` or, preferably, cloned into the Linux filesystem for speed.

## Decision note

Working directly on `/mnt/c/...` from WSL2 is slow for Python imports and pytest. Recommended in G01: keep the canonical checkout on the Windows side for the editor, but create the virtualenvs inside the Linux filesystem (for example `~/.venvs/skuld`), or move the whole checkout to `~/skuld` and open it from Windows via `\\wsl$`. Decide and record here.
