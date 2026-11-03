#!/usr/bin/env bash
# Exercise SymPort against the REAL symbian-platform SDK (not the test doubles).
# Needs: `symbian` on PATH (pip install symbian-platform), clang++ with ARM target, ld.lld, cmake, pip.
# Builds the SDK's own freestanding E32 probe for ARMv5T, packages it, and cross-checks SymPort's
# E32/SIS parsers against the SDK's native inspector. Writes JSON reports to build/reports/real-sdk-*.json.
#   tools/sdk/verify-real-sdk.sh [workdir]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${1:-$ROOT/build/real-sdk}"
REPORTS="$ROOT/build/reports"
command -v symbian >/dev/null || { echo "symbian CLI not found: pip install symbian-platform" >&2; exit 3; }
mkdir -p "$WORK/toolbin" "$REPORTS"

# The SDK looks for ninja NEXT TO the compiler first and needs ninja >= 1.12: build a private tool directory.
python3 -m venv "$WORK/ninja-venv" >/dev/null
"$WORK/ninja-venv/bin/pip" install -q --only-binary=:all: ninja
# Resolve a tool by plain name, then by versioned names (clang++-18, ld.lld-18 ...); fail with a clear message.
find_tool() {
  local name="$1" found
  found="$(command -v "$name" || true)"
  if [ -z "$found" ]; then
    found="$(compgen -c "$name-" 2>/dev/null | grep -E "^$name-[0-9]+$" | sort -t- -k2 -n | tail -1 || true)"
    [ -n "$found" ] && found="$(command -v "$found")"
  fi
  if [ -z "$found" ]; then
    echo "required tool not found: $name (install clang, lld and cmake)" >&2
    exit 3
  fi
  printf '%s\n' "$found"
}
for t in clang++ ld.lld cmake; do ln -sf "$(find_tool "$t")" "$WORK/toolbin/$t"; done
ln -sf "$WORK/ninja-venv/bin/ninja" "$WORK/toolbin/ninja"

# The probe project lives only in the SDK's source tree (public repo, read-only shallow clone).
if [ ! -d "$WORK/symbian-platform/probes/e32_probe" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 https://github.com/hpnkv/symbian-platform "$WORK/symbian-platform"
fi
rm -rf "$WORK/e32_probe" && cp -r "$WORK/symbian-platform/probes/e32_probe" "$WORK/e32_probe"

export PATH="$WORK/toolbin:$PATH"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
SP=(python3 -m symport)
"${SP[@]}" doctor --json --report "$REPORTS/real-sdk-doctor.json" >/dev/null
"${SP[@]}" app build --project "$WORK/e32_probe" --mode toolchain \
    --compiler "$WORK/toolbin/clang++" --linker "$WORK/toolbin/ld.lld" --report "$REPORTS/real-sdk-build.json"
"${SP[@]}" app package --project "$WORK/e32_probe" --report "$REPORTS/real-sdk-package.json"
"${SP[@]}" app analyze "$WORK/e32_probe" --cross-check --report "$REPORTS/real-sdk-analyze.json"
"${SP[@]}" sis inspect "$WORK/e32_probe/.symbian/package/probe.sis" --report "$REPORTS/real-sdk-sis.json"
echo "OK: reports in $REPORTS (static checks only; nothing was run on a phone or emulator)"
