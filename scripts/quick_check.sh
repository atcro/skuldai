#!/usr/bin/env bash
# Format the given paths, lint everything, run the whole test suite (sim venv). Usage:
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/quick_check.sh [paths to ruff-format...]
set -uo pipefail
VENV="$HOME/.venvs/skuld-mujoco"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd /mnt/c/Skuld
if [ "$#" -gt 0 ]; then ruff format "$@"; fi
ruff check . ; echo "ruff exit: $?"
python -m pytest -q -ra; echo "pytest exit: $?"
