#!/usr/bin/env bash
# Собирает под Linux инструменты Symbian из tools/s60/vendor:
#   bin/skc     — Nokia Skin Data Compiler (skin .txt -> .skn, .pkg, список для mif/mbm)
#   bin/bmconv  — Symbian bmconv (BMP -> .mbm)
# Нужны только g++ и make-совместимая оболочка. Исходники вендора не меняются.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/bin"; WORK="$HERE/.build"
CXX="${CXX:-g++}"
mkdir -p "$BIN" "$WORK"

# ---------- skc (Nokia Skin Data Compiler)
SK="$HERE/vendor/nokia-skin-compiler"
cat > "$WORK/compat.h" <<'H'
#include <cstring>
#include <ctime>
#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <climits>
#include <strings.h>
H
"$CXX" -O1 -w -fpermissive -std=gnu++14 -include "$WORK/compat.h" \
  -DRD_ENHANCED_SKINNING -DRD_SCALABLE_UI -D__SERIES60_31__ \
  -I "$SK/sdcinc" -I "$SK/include" "$SK"/sdcsrc/*.cpp -o "$BIN/skc"

# ---------- bmconv
# В исходнике `long` = 32 бита (Windows); на 64-bit Linux структуры файла
# разъехались бы, поэтому на копии `long` заменяется на `int`.
BM="$HERE/vendor/bmconv"; BMW="$WORK/bmconv_src"
rm -rf "$BMW"; mkdir -p "$BMW"
for f in "$BM"/*.CPP "$BM"/*.H; do
  sed -E 's/\blong[[:space:]]+(unsigned[[:space:]]+)?int\b/\1int/g; s/\blong[[:space:]]+unsigned\b/unsigned int/g; s/\blong\b/int/g' "$f" > "$BMW/$(basename "$f")"
done
sed -i 's/(foundPath > 0)/(foundPath != 0)/' "$BMW/PBMCOMP.CPP"
echo 'static const char version[] = "linux-build (SymbianSource oss.FCL.sf.os.graphics)";' > "$BMW/TOOLSVER.H"
cat > "$BMW/pre.h" <<'H'
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <assert.h>
#include <fstream>
#include <iostream>
#include <ostream>
#include <string>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
using namespace std;
H
(cd "$BMW" && "$CXX" -O1 -w -fpermissive -std=gnu++14 -D__LINUX__ -D__TOOLS2__ -I. -include pre.h *.CPP -o "$BIN/bmconv")

echo "OK: $BIN/skc, $BIN/bmconv"
