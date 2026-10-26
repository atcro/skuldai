#!/usr/bin/env bash
# G01 toolchain bootstrap for WSL2 Ubuntu 24.04. Needs sudo; a human runs it.
# Package list follows the runbook G01 step 11 (DOC-VERIFIED) plus the Mesa GL
# libraries MuJoCo needs for offscreen rendering (PROPOSED).
#
# Run inside an Ubuntu terminal:
#     sudo bash /mnt/c/Skuld/scripts/bootstrap_wsl.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  git git-lfs curl wget jq unzip zip ca-certificates \
  build-essential cmake \
  python3 python3-pip python3-venv python3-dev \
  ffmpeg \
  libgl1 libegl1 libosmesa6 libglu1-mesa

git lfs install --system

echo
echo "bootstrap complete:"
python3 --version
python3 -m pip --version
python3 -c 'import venv, ensurepip; print("venv+ensurepip ok")'
git --version
ffmpeg -version | head -1
jq --version
gcc --version | head -1
