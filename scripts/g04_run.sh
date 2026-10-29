#!/usr/bin/env bash
# G04 inside WSL2. Usage:
#   step A (read-only):  wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh catalog
#   step B (one call):   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh propose nvidia/<model-id>
#   step C (sim venv):   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh execute "Name"
# The key is read from /mnt/c/Skuld/.env (NEBIUS_TOKEN_FACTORY_API_KEY) and exported under the
# name the npa CLI documents (NEBIUS_TOKEN_FACTORY_KEY). It is never echoed or written.
set -uo pipefail
REPO=/mnt/c/Skuld
OUT="$REPO/evidence/G04"
cd "$REPO"
mkdir -p "$OUT"
if [ -f .env ]; then set -a; # shellcheck disable=SC1090
  source <(tr -d '\r' < ./.env); set +a; fi
export NEBIUS_TOKEN_FACTORY_KEY="${NEBIUS_TOKEN_FACTORY_API_KEY:-}"
if [ -z "$NEBIUS_TOKEN_FACTORY_KEY" ]; then echo "NEBIUS_TOKEN_FACTORY_API_KEY not in .env"; exit 2; fi
PREFIX="${NEBIUS_TOKEN_FACTORY_KEY:0:12}"
scan() { if grep -rqsF -- "$PREFIX" "$OUT" || grep -rqsE "Bearer [A-Za-z0-9._-]{20,}" "$OUT"; then echo "SECRET PATTERN FOUND IN $OUT: scrub before commit"; fi; }

case "${1:-}" in
  catalog)
    # shellcheck disable=SC1091
    source "$HOME/.venvs/npa/bin/activate"
    echo "=== npa workbench token-factory status ==="
    npa workbench token-factory status --output json 2>&1 | sed "s#$NEBIUS_TOKEN_FACTORY_KEY#<redacted>#g" | tee "$OUT/npa-status.json"
    echo "=== npa workbench token-factory verify (live models call, not inference) ==="
    npa workbench token-factory verify --output json 2>&1 | sed "s#$NEBIUS_TOKEN_FACTORY_KEY#<redacted>#g" | tee "$OUT/npa-verify.json"
    echo "verify exit: ${PIPESTATUS[0]}"
    echo "=== npa workbench token-factory models ==="
    npa workbench token-factory models --output json 2>&1 | sed "s#$NEBIUS_TOKEN_FACTORY_KEY#<redacted>#g" > "$OUT/npa-models.json"
    echo "models exit: ${PIPESTATUS[0]}; $(wc -c < "$OUT/npa-models.json") bytes"
    # shellcheck disable=SC1091
    source "$HOME/.venvs/skuld/bin/activate"
    echo "=== direct GET /v1/models?verbose=true (pricing, status) ==="
    python scripts/g04_models.py --out "$OUT"
    scan ;;
  propose)
    # shellcheck disable=SC1091
    source "$HOME/.venvs/npa/bin/activate"
    python -m pip install -q -e "$REPO" 2>&1 | tail -1   # skuld package into the npa venv (pure parts only)
    python scripts/g04_run.py propose --out "$OUT" --model "${2:-}" 2>&1 | tee -a "$OUT/g04_run.log"
    echo "propose exit: ${PIPESTATUS[0]}"
    scan ;;
  execute)
    # shellcheck disable=SC1091
    source "$HOME/.venvs/skuld-mujoco/bin/activate"
    export SKULD_MENAGERIE_DIR="${SKULD_MENAGERIE_DIR:-$HOME/src/mujoco_menagerie}" MUJOCO_GL="${MUJOCO_GL:-egl}"
    python scripts/g04_run.py execute --out "$OUT" --approved-by "${2:?name required}" --menagerie "$SKULD_MENAGERIE_DIR" 2>&1 | tee -a "$OUT/g04_run.log"
    echo "execute exit: ${PIPESTATUS[0]}"
    scan ;;
  *) echo "usage: g04_run.sh catalog | propose <nvidia/model> | execute <approver name>"; exit 2 ;;
esac
