#!/usr/bin/env bash
# G04 step 1: pinned checkout of nebius-physical-ai and an isolated npa venv (no key needed).
# Usage: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_setup.sh
# Writes evidence/G04/npa-pin.txt, npa-version.txt, npa-token-factory-help.txt. No network calls
# to Token Factory happen here; this only clones GitHub and installs the CLI locally.
set -uo pipefail
REPO=/mnt/c/Skuld
SRC="$HOME/src/nebius-physical-ai"
VENV="$HOME/.venvs/npa"
OUT="$REPO/evidence/G04"
mkdir -p "$OUT"
if [ ! -d "$SRC/.git" ]; then
  git clone --quiet https://github.com/nebius/nebius-physical-ai.git "$SRC" || { echo "clone failed"; exit 1; }
fi
cd "$SRC"
COMMIT=$(git rev-parse HEAD)
{
  echo "repo: https://github.com/nebius/nebius-physical-ai"
  echo "commit: $COMMIT"
  echo "cloned_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "path: $SRC"
} > "$OUT/npa-pin.txt"
cat "$OUT/npa-pin.txt"
if [ ! -x "$VENV/bin/python" ]; then python3 -m venv "$VENV" || { echo "venv failed"; exit 1; }; fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip 2>&1 | tail -1
python -m pip install -q -e npa 2>&1 | tail -3
echo "pip exit: ${PIPESTATUS[0]}"
npa --version 2>&1 | tee "$OUT/npa-version.txt"
echo "=== npa workbench token-factory --help ==="
npa workbench token-factory --help 2>&1 | tee "$OUT/npa-token-factory-help.txt"
for sub in status verify models generate; do
  echo "=== npa workbench token-factory $sub --help ==="
  npa workbench token-factory "$sub" --help 2>&1
done | tee -a "$OUT/npa-token-factory-help.txt"
sed -n 1,80p "$SRC/docs/workbench/token-factory.md" > "$OUT/token-factory-doc-head.txt"
echo "done"
