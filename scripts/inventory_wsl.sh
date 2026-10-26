#!/usr/bin/env bash
# G01 inventory inside WSL2 Ubuntu. Prints versions only; no secrets.
# Usage (from Windows): wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/inventory_wsl.sh
set -u
echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "user: $(whoami)"
echo "kernel: $(uname -a)"
. /etc/os-release && echo "os: $PRETTY_NAME"
echo "nproc: $(nproc)"
echo "mem: $(free -h | awk 'NR==2{print $2" total, "$7" available"}')"
echo "disk_home: $(df -h ~ | awk 'NR==2{print $4" free of "$2}')"
echo "python3: $(python3 --version 2>&1)"
echo "python3_venv: $(python3 -c 'import venv, ensurepip; print("ok")' 2>&1 | tail -1)"
echo "pip: $(python3 -m pip --version 2>&1 | tail -1)"
echo "git: $(git --version 2>&1)"
echo "curl: $(curl --version 2>&1 | head -1 | cut -d' ' -f1-2)"
echo "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
echo "jq: $(jq --version 2>&1)"
echo "gcc: $(gcc --version 2>&1 | head -1)"
echo "cmake: $(cmake --version 2>&1 | head -1)"
echo "node: $(node --version 2>&1)"
echo "docker: $(docker --version 2>&1 | head -1)"
echo "claude: $(claude --version 2>&1 | head -1)"
echo "nebius_cli: $(command -v nebius >/dev/null 2>&1 && nebius version 2>&1 | head -1 || echo 'not installed')"
echo "npa: $(command -v npa >/dev/null 2>&1 && npa --version 2>&1 | head -1 || echo 'not installed')"
if sudo -n true 2>/dev/null; then echo "sudo: passwordless"; else echo "sudo: needs password"; fi
echo "repo_mount: $(test -f /mnt/c/Skuld/spec.md && echo '/mnt/c/Skuld visible' || echo '/mnt/c/Skuld NOT visible')"
echo "gl: $(command -v glxinfo >/dev/null 2>&1 && glxinfo -B 2>&1 | grep -i 'opengl renderer' || echo 'glxinfo not installed')"
echo "wslg_display: ${DISPLAY:-unset} wayland=${WAYLAND_DISPLAY:-unset}"
