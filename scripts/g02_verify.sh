#!/usr/bin/env bash
# G02 verification inside WSL2 Ubuntu: lint, tests, pinned lock, evidence.
# Usage (from Windows PowerShell): wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g02_verify.sh
set -uo pipefail

REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld"
EVID="$REPO/evidence/G02"
mkdir -p "$EVID"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"

step() { echo; echo "=== $* ==="; }

step "reinstall editable (picks up new modules)"
python -m pip install -e ".[dev]" -q 2>&1 | tail -3
echo "python: $(python --version)"

step "ruff"
ruff check . 2>&1 | tee "$EVID/ruff.txt"
RUFF_EXIT=${PIPESTATUS[0]}
echo "ruff exit: $RUFF_EXIT" | tee -a "$EVID/ruff.txt"

step "pytest"
python -m pytest -q -ra 2>&1 | tee "$EVID/tests.txt"
PYTEST_EXIT=${PIPESTATUS[0]}
echo "pytest exit: $PYTEST_EXIT" | tee -a "$EVID/tests.txt"

step "pinned lock"
python -m pip freeze --exclude-editable > "$REPO/requirements.lock.txt"
cp "$REPO/requirements.lock.txt" "$EVID/requirements.lock.txt"
echo "$(wc -l < "$REPO/requirements.lock.txt") pinned packages -> requirements.lock.txt"

step "summary"
echo "ruff exit: $RUFF_EXIT"
echo "pytest exit: $PYTEST_EXIT"
[[ "$RUFF_EXIT" == "0" && "$PYTEST_EXIT" == "0" ]] && echo "G02 LOCAL CHECKS: PASS" || echo "G02 LOCAL CHECKS: FAIL"
