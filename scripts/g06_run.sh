#!/usr/bin/env bash
# G06 evidence run inside WSL2 (app venv; no MuJoCo needed). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g06_run.sh [--approved-by NAME]
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev]" -q 2>&1 | tail -2
mkdir -p evidence/G06

echo "=== ruff ==="; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (app venv; MuJoCo tests skip here) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G06/tests-app-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g06_run.py ==="
python scripts/g06_run.py --g05 evidence/G05 --out evidence/G06 "$@" 2>&1 | tee evidence/G06/g06_run.log
echo "run exit: ${PIPESTATUS[0]}"
