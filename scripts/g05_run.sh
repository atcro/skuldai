#!/usr/bin/env bash
# G05 evidence run inside WSL2 (simulator venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g05_run.sh [extra args to g05_run.py]
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
# remove outputs of any earlier run so nothing stale survives a crash mid-run
rm -f evidence/G05/*.mp4 evidence/G05/*.trajectory.json evidence/G05/g05_run_report.json

echo "=== ruff ==="; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv, includes mujoco tests) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G05/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g05_run.py ==="
python scripts/g05_run.py --menagerie "$SKULD_MENAGERIE_DIR" --out evidence/G05 "$@" 2>&1 | tee evidence/G05/g05_run.log
echo "run exit: ${PIPESTATUS[0]}"
ls -la evidence/G05
