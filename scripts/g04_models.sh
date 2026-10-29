#!/usr/bin/env bash
# G04 step 2 wrapper: read-only catalog listing in the app venv. Key stays in .env.
# Usage: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_models.sh
set -uo pipefail
# shellcheck disable=SC1091
source "$HOME/.venvs/skuld/bin/activate"
cd /mnt/c/Skuld
python scripts/g04_models.py --out evidence/G04
echo "exit: $?"
# never let the key leak into evidence: check for bearer tokens and for the key's own prefix
PREFIX=$(tr -d '\r' < .env | sed -n 's/^NEBIUS_TOKEN_FACTORY_API_KEY=//p' | head -c 12)
if grep -rqsE "Bearer [A-Za-z0-9._-]{20,}" evidence/G04; then echo "SECRET PATTERN (bearer) FOUND IN EVIDENCE"; fi
if [ -n "$PREFIX" ] && grep -rqsF -- "$PREFIX" evidence/G04; then echo "SECRET PATTERN (key prefix) FOUND IN EVIDENCE"; fi
