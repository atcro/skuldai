#!/usr/bin/env bash
# Serve the dashboard over evidence/ until stopped (Ctrl-C or kill). Read-only; no simulator run.
# Usage: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/dashboard_serve.sh [port]
# Then open http://127.0.0.1:8765/ , /atlas , /counterexample , /release in a Windows browser.
set -uo pipefail
VENV="$HOME/.venvs/skuld-mujoco"
[ -x "$VENV/bin/uvicorn" ] || VENV="$HOME/.venvs/skuld"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd /mnt/c/Skuld
exec uvicorn skuld.api.main:app --host 127.0.0.1 --port "${1:-8765}" --log-level info
