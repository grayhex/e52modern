#!/usr/bin/env bash
# Installs apt packages on a CI runner with a hard time limit per attempt and a few retries.
# Some runners are routed to a very slow package mirror (a few KB/s). The first attempt uses the runner's default
# mirror; if it stalls, the retries switch to archive.ubuntu.com. Downloaded .deb files stay in the apt cache, so
# every retry resumes where the previous attempt stopped instead of hanging until the job timeout.
#   tools/ci/apt-install.sh g++ ffmpeg
set -uo pipefail
[ $# -gt 0 ] || { echo "usage: $0 package..." >&2; exit 2; }

use_fallback_mirror() {
  # Ubuntu runner images list their mirrors in /etc/apt/apt-mirrors.txt (one URL per line).
  if [ -w /etc/apt/apt-mirrors.txt ] || sudo test -f /etc/apt/apt-mirrors.txt; then
    echo "http://archive.ubuntu.com/ubuntu/ priority:1" | sudo tee /etc/apt/apt-mirrors.txt >/dev/null
    echo "apt: switched to archive.ubuntu.com" >&2
  fi
}

for attempt in 1 2 3 4; do
  [ "$attempt" -eq 2 ] && use_fallback_mirror
  limit=$((attempt == 1 ? 150 : 240))
  if timeout "$limit" sudo apt-get update -o Acquire::Retries=3 \
     && timeout "$limit" sudo apt-get install -y --no-install-recommends -o Acquire::Retries=3 "$@"; then
    exit 0
  fi
  echo "apt attempt $attempt failed or timed out; retrying" >&2
  sleep $((attempt * 5))
done
echo "Could not install: $*" >&2
exit 1
