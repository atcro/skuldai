#!/usr/bin/env bash
# G08 inside WSL2 (sim venv, which also has tavily-python). Usage:
#   phase 1: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g08_run.sh
#   phase 2: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g08_run.sh --approved-by "Name"
# TAVILY_API_KEY is read from /mnt/c/Skuld/.env (git-ignored) if present; it is never echoed.
set -uo pipefail
REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO"
if [ -f .env ]; then
  # tolerate a CRLF .env written from Windows: strip CRs before exporting
  set -a; # shellcheck disable=SC1090
  source <(tr -d '\r' < ./.env); set +a
fi
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -2
mkdir -p evidence/G08

echo "=== ruff ==="; ruff check . ; echo "ruff exit: $?"
echo "=== pytest (sim venv) ==="
python -m pytest -q -ra 2>&1 | tee evidence/G08/tests-sim-venv.txt
echo "pytest exit: ${PIPESTATUS[0]}"
echo "=== g08_run.py $* ==="
if [ "$#" -gt 0 ]; then
  python scripts/g08_run.py --menagerie "$SKULD_MENAGERIE_DIR" "$@" 2>&1 | tee -a evidence/G08/g08_run.log
else
  python scripts/g08_run.py 2>&1 | tee -a evidence/G08/g08_run.log
fi
echo "run exit: ${PIPESTATUS[0]}"
# never let a key leak into evidence
if grep -rqs "tvly-" evidence/G08; then echo "SECRET PATTERN FOUND IN EVIDENCE: scrub before commit"; fi
