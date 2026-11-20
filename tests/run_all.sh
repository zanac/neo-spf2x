#!/bin/sh
# Runs every test.  Without arguments only ROM-free tests run.
#   tests/run_all.sh                    synthetic game
#   tests/run_all.sh /path/to/romdir    also the real romset (samsho3 recipe)
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== python packer tests"
if [ $# -ge 1 ]; then
    NGPK_ROMDIR=$1 python3 -I "$ROOT/tests/test_ngpk.py"
else
    python3 -I "$ROOT/tests/test_ngpk.py"
fi

echo "== firmware loader, synthetic game"
python3 -I "$ROOT/tests/make_synthetic.py" "$WORK/syn"
python3 -I "$ROOT/tools/ngpk.py" unpack "$WORK/syn/synthetic.ngpk" -o "$WORK/syn/unpacked" >/dev/null
python3 -I "$ROOT/tools/mkstub.py" "$WORK/syn/unpacked/P.bin" -o "$WORK/syn/boot.bin" >/dev/null
make -s -C "$ROOT/firmware" test PACK="$WORK/syn/synthetic.ngpk" UNPACKED="$WORK/syn/unpacked" CANON="$WORK/syn/synthetic_canonical.ngpk" BOOT="$WORK/syn/boot.bin"

if [ $# -ge 1 ]; then
    echo "== firmware loader, real romset"
    python3 -I "$ROOT/tools/ngpk.py" pack "$ROOT/recipes/samsho3.json" --base-dir "$1" -o "$WORK/real.ngpk" >/dev/null
    python3 -I "$ROOT/tools/ngpk.py" unpack "$WORK/real.ngpk" -o "$WORK/real_unpacked" >/dev/null
    make -s -C "$ROOT/firmware" test PACK="$WORK/real.ngpk" UNPACKED="$WORK/real_unpacked"
fi
make -s -C "$ROOT/firmware" clean
if command -v iverilog >/dev/null 2>&1; then
    echo "== gateware, sprite fetch/serializer"
    python3 -I "$ROOT/gateware/tests/test_cfetch.py"
    python3 -I "$ROOT/gateware/tests/test_modules.py"
    python3 -I "$ROOT/gateware/tests/test_system.py"
    python3 -I "$ROOT/gateware/tests/test_mvs.py"
    python3 -I "$ROOT/gateware/tests/test_io.py"
else
    echo "== gateware tests skipped (iverilog not installed)"
fi
echo "== documentation EN/IT in step"
python3 -I "$ROOT/tests/check_docs.py"
echo "== ALL OK"
