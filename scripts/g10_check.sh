#!/usr/bin/env bash
# Lint + unit tests only (sim venv), no simulator run. Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g10_check.sh
set -uo pipefail
VENV="$HOME/.venvs/skuld-mujoco"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd /mnt/c/Skuld
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}" MUJOCO_GL="${MUJOCO_GL:-egl}"
ruff format skuld/search tests/test_search.py scripts/g10_run.py; echo "format exit: $?"
ruff check . ; echo "ruff exit: $?"
python -m pytest -q -ra; echo "pytest exit: $?"
