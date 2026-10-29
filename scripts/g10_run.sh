#!/usr/bin/env bash
# G10 evidence run inside WSL2 (simulator venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g10_run.sh [--no-video] [--no-hypothesis]
# Reads the archived G07 baseline; never re-runs or edits it.
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
rm -rf evidence/G10
mkdir -p evidence/G10

HYP=(--hypothesis evidence/G08/hypothesis.json)
ARGS=()
for a in "$@"; do
  if [ "$a" = "--no-hypothesis" ]; then HYP=(); else ARGS+=("$a"); fi
done

echo "=== ruff ==="; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G10/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g10_run.py ==="
python scripts/g10_run.py --menagerie "$SKULD_MENAGERIE_DIR" --out evidence/G10 \
  --baseline evidence/G07 "${HYP[@]}" "${ARGS[@]}" 2>&1 | tee evidence/G10/g10_run.log
echo "run exit: ${PIPESTATUS[0]}"
du -sh evidence/G10
