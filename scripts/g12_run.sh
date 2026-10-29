#!/usr/bin/env bash
# G12 frozen rerun inside WSL2 (simulator venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g12_run.sh
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
rm -rf evidence/G12
mkdir -p evidence/G12
echo "=== ruff ==="; ruff format scripts/g12_run.py >/dev/null; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G12/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== pip freeze ==="; python -m pip freeze > evidence/G12/requirements.sim.freeze.txt
echo "=== g12_run.py ==="
python scripts/g12_run.py --menagerie "$SKULD_MENAGERIE_DIR" --out evidence/G12 2>&1 | tee evidence/G12/g12_run.log
echo "run exit: ${PIPESTATUS[0]}"
du -sh evidence/G12
