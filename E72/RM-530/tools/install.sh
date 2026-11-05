#!/usr/bin/env bash
# Local Docker deployment; preserves existing settings and named volumes.
set -euo pipefail
cd "$(dirname "$0")/.."
profile=()
build=(--build)
check=0
for argument in "$@"; do
  case "$argument" in
    --emulator) profile=(--profile emulator) ;;
    --no-build) build=() ;;
    --check) check=1 ;;
    *) echo 'Usage: tools/install.sh [--emulator] [--no-build] [--check]' >&2; exit 2 ;;
  esac
done
command -v docker >/dev/null || { echo 'Install Docker Engine / Desktop with Linux containers and Compose v2.' >&2; exit 1; }
docker compose version >/dev/null
docker info >/dev/null
if [[ ! -f .env && "$check" -eq 0 ]]; then
  install -m 600 .env.example .env
fi
docker compose "${profile[@]}" config --quiet
if [[ "$check" -eq 1 ]]; then
  echo 'Compose valid. No services, files or volumes changed.'
  exit 0
fi
docker compose "${profile[@]}" up -d "${build[@]}"
ready=0
for ((attempt=0; attempt<40; attempt++)); do
  if docker compose exec -T workbench python -c 'import os,urllib.request; urllib.request.urlopen("http://127.0.0.1:"+os.getenv("SYMPORT_HTTP_PORT","8765")+"/api/state",timeout=2).read()' >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[[ "$ready" -eq 1 ]] || { docker compose ps; echo 'Workbench not ready; inspect docker compose logs workbench.' >&2; exit 1; }
docker compose exec -T workbench python -c 'import os; print("SymPort: http://127.0.0.1:"+os.getenv("SYMPORT_HTTP_PORT","8765"))'
echo 'Remote access: forward that same port over SSH. Firmware and phone connection are configured in the UI/docs.'
