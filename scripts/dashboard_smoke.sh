#!/usr/bin/env bash
# Start the dashboard, fetch the four surfaces and /health, record sizes and status codes, stop it.
# Usage: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/dashboard_smoke.sh [outfile]
set -uo pipefail
VENV="$HOME/.venvs/skuld-mujoco"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd /mnt/c/Skuld
OUT="${1:-evidence/G12/dashboard_smoke.txt}"
mkdir -p "$(dirname "$OUT")"
uvicorn skuld.api.main:app --host 127.0.0.1 --port 8765 --log-level warning &
PID=$!
for _ in $(seq 1 30); do curl -fs http://127.0.0.1:8765/health >/dev/null 2>&1 && break; sleep 0.5; done
{
  echo "dashboard smoke $(date -u +%Y-%m-%dT%H:%M:%SZ) commit $(git rev-parse --short HEAD)"
  for path in /health / "/atlas?x=observation_delay_ms&y=object_mass_kg" /counterexample /release "/evidence/G10/comparison.svg"; do
    code=$(curl -s -o /tmp/skuld_page -w "%{http_code}" "http://127.0.0.1:8765$path")
    bytes=$(wc -c < /tmp/skuld_page)
    echo "GET $path -> $code, $bytes bytes"
  done
  echo "release page shows for v1:"; curl -s http://127.0.0.1:8765/release | grep -o 'status-big [A-Z]*' | head -2
  echo "missing-record warnings:"; curl -s http://127.0.0.1:8765/ | grep -c "Records not found" || true
} | tee "$OUT"
kill $PID 2>/dev/null; wait $PID 2>/dev/null
