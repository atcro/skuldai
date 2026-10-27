#!/usr/bin/env bash
# G05 setup inside WSL2 Ubuntu: simulator venv, pinned sparse clone of MuJoCo
# Menagerie (Panda only), and a headless MuJoCo smoke check with evidence.
# No sudo, no secrets, network: PyPI + GitHub clone only.
# Usage: wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g05_setup.sh
set -uo pipefail

REPO=/mnt/c/Skuld
VENV="$HOME/.venvs/skuld-mujoco"
MENAGERIE="$HOME/src/mujoco_menagerie"     # downloaded assets stay outside the repo
EVID="$REPO/evidence/G05"
mkdir -p "$EVID" "$HOME/src"

step() { echo; echo "=== $* ==="; }

step "simulator venv at $VENV"
if [[ ! -d "$VENV" ]]; then python3 -m venv "$VENV"; fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip -q
cd "$REPO"
# skuld[dev] gives the schemas the adapter codes against; [sim] adds mujoco.
python -m pip install -e ".[dev,sim]" -q 2>&1 | tail -3
python -m pip install pillow -q
python -c 'import mujoco, numpy; print("mujoco", mujoco.__version__, "numpy", numpy.__version__)'
python -m pip freeze --exclude-editable > "$EVID/requirements.sim.freeze.txt"

step "MuJoCo Menagerie sparse clone (franka_emika_panda only)"
if [[ ! -d "$MENAGERIE/.git" ]]; then
  git clone --filter=blob:none --sparse --quiet \
    https://github.com/google-deepmind/mujoco_menagerie.git "$MENAGERIE"
fi
git -C "$MENAGERIE" sparse-checkout set franka_emika_panda
MENAGERIE_COMMIT=$(git -C "$MENAGERIE" rev-parse HEAD)
echo "menagerie commit: $MENAGERIE_COMMIT"
{
  echo "repo: https://github.com/google-deepmind/mujoco_menagerie"
  echo "commit: $MENAGERIE_COMMIT"
  echo "cloned_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "path: $MENAGERIE"
  echo "sparse: franka_emika_panda"
  echo "files:"
  (cd "$MENAGERIE" && find franka_emika_panda -maxdepth 1 -type f | sort | sed 's/^/  /')
} > "$EVID/menagerie-pin.txt"
cat "$EVID/menagerie-pin.txt"

step "Panda model license"
LIC="$MENAGERIE/franka_emika_panda/LICENSE"
if [[ -f "$LIC" ]]; then
  cp "$LIC" "$EVID/panda-model-LICENSE.txt"
  echo "license head:"; head -5 "$LIC"
else
  echo "WARNING: no LICENSE file in franka_emika_panda/" | tee "$EVID/panda-model-LICENSE.txt"
fi

step "headless smoke check (MUJOCO_GL=egl)"
MUJOCO_GL=egl python "$REPO/scripts/mujoco_check.py" "$MENAGERIE" "$EVID/panda-frame.png" \
  | tee "$EVID/mujoco-smoke-egl.json"
EGL_EXIT=${PIPESTATUS[0]}
echo "egl exit: $EGL_EXIT"
if [[ "$EGL_EXIT" != "0" ]]; then
  step "retry with MUJOCO_GL=osmesa"
  MUJOCO_GL=osmesa python "$REPO/scripts/mujoco_check.py" "$MENAGERIE" "$EVID/panda-frame.png" \
    | tee "$EVID/mujoco-smoke-osmesa.json"
  echo "osmesa exit: ${PIPESTATUS[0]}"
fi

step "summary"
echo "venv: $VENV"
echo "menagerie: $MENAGERIE @ $MENAGERIE_COMMIT"
ls -la "$EVID"
