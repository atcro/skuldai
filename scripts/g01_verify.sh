#!/usr/bin/env bash
# G01 verification inside WSL2 Ubuntu. No sudo, no secrets, no network beyond PyPI.
# Creates the app venv in the Linux filesystem (fast), installs the package from the
# Windows-side checkout, runs lint + tests, starts the API and captures GET /health.
# Usage (from Windows PowerShell): wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g01_verify.sh
set -uo pipefail

REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld"
EVID="$REPO/evidence/G01"
mkdir -p "$EVID"

step() { echo; echo "=== $* ==="; }

step "versions after bootstrap"
bash "$REPO/scripts/inventory_wsl.sh" | tee "$EVID/versions-wsl-ubuntu-after-apt.txt"

step "create venv at $VENV"
python3 -m venv "$VENV" || { echo "venv creation failed"; exit 1; }
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip -q
echo "python: $(python --version)   pip: $(python -m pip --version | cut -d' ' -f1-2)"

step "install skuld[dev] (editable)"
cd "$REPO"
python -m pip install -e ".[dev]" -q 2>&1 | tail -5
python -m pip freeze > "$EVID/requirements.freeze.txt"
echo "frozen $(wc -l < "$EVID/requirements.freeze.txt") packages -> evidence/G01/requirements.freeze.txt"

step "ruff"
ruff check . 2>&1 | tee "$EVID/ruff.txt"
echo "ruff exit: ${PIPESTATUS[0]}" | tee -a "$EVID/ruff.txt"

step "pytest"
python -m pytest -q 2>&1 | tee "$EVID/tests.txt"
PYTEST_EXIT=${PIPESTATUS[0]}
echo "pytest exit: $PYTEST_EXIT" | tee -a "$EVID/tests.txt"

step "GET /health against a live uvicorn"
uvicorn skuld.api.main:app --host 127.0.0.1 --port 8765 --log-level warning &
UV_PID=$!
HEALTH_CODE=000
for _ in $(seq 1 30); do
  HEALTH_CODE=$(curl -s -o "$EVID/health.json" -w "%{http_code}" http://127.0.0.1:8765/health || true)
  [[ "$HEALTH_CODE" == "200" ]] && break
  sleep 0.5
done
kill "$UV_PID" 2>/dev/null; wait "$UV_PID" 2>/dev/null
echo "health http: $HEALTH_CODE"
cat "$EVID/health.json" 2>/dev/null; echo

step "summary"
echo "venv: $VENV"
echo "pytest exit: $PYTEST_EXIT"
echo "health http: $HEALTH_CODE"
[[ "$PYTEST_EXIT" == "0" && "$HEALTH_CODE" == "200" ]] && echo "G01 CHECKS: PASS" || echo "G01 CHECKS: FAIL"
