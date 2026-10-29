#!/usr/bin/env bash
# G11 evidence run inside WSL2 (simulator venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g11_run.sh [--no-video]
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
rm -rf evidence/G11
mkdir -p evidence/G11

echo "=== ruff ==="; ruff format skuld/release skuld/policies/push_controller_v2.py scripts/g11_run.py >/dev/null; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G11/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g11_run.py ==="
python scripts/g11_run.py --menagerie "$SKULD_MENAGERIE_DIR" --out evidence/G11 --g10 evidence/G10 "$@" 2>&1 | tee evidence/G11/g11_run.log
echo "run exit: ${PIPESTATUS[0]}"
du -sh evidence/G11
