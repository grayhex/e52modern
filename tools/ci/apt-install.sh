#!/usr/bin/env bash
# Installs apt packages on a CI runner with a hard time limit per attempt and a few retries.
# Some runners are routed to a very slow package mirror; downloaded .deb files stay in the apt cache, so every
# retry resumes where the previous attempt stopped instead of hanging until the job timeout.
#   tools/ci/apt-install.sh g++ ffmpeg
set -uo pipefail
[ $# -gt 0 ] || { echo "usage: $0 package..." >&2; exit 2; }
for attempt in 1 2 3 4; do
  if timeout 240 sudo apt-get update -o Acquire::Retries=3 \
     && timeout 240 sudo apt-get install -y --no-install-recommends -o Acquire::Retries=3 "$@"; then
    exit 0
  fi
  echo "apt attempt $attempt failed or timed out; retrying" >&2
  sleep $((attempt * 5))
done
echo "Could not install: $*" >&2
exit 1
