#!/usr/bin/env bash
# G07 evidence run inside WSL2 (simulator venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g07_run.sh [--no-video]
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
rm -rf evidence/G07
mkdir -p evidence/G07

echo "=== ruff ==="; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G07/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g07_run.py ==="
python scripts/g07_run.py --menagerie "$SKULD_MENAGERIE_DIR" --out evidence/G07 "$@" 2>&1 | tee evidence/G07/g07_run.log
echo "run exit: ${PIPESTATUS[0]}"
du -sh evidence/G07
