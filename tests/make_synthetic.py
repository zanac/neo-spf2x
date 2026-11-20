#!/usr/bin/env python3
"""Build a ROM-free synthetic game (realistic region sizes) for CI runs.

    make_synthetic.py outdir      -> outdir/synthetic.ngpk
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import ngpk  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    rnd = random.Random(7)
    p = bytearray(rnd.randbytes(3 * 1024 * 1024))
    p[0x100:0x107] = b"NEO-GEO"
    files = {
        "p.bin": ngpk.swap16(bytes(p)),
        "c1.bin": rnd.randbytes(2 * 1024 * 1024),
        "c2.bin": rnd.randbytes(2 * 1024 * 1024),
        "s.bin": rnd.randbytes(128 * 1024),
        "m.bin": rnd.randbytes(128 * 1024),
        "v.bin": rnd.randbytes(1024 * 1024 + 300),  # not sector aligned
    }
    for n, d in files.items():
        with open(os.path.join(out, n), "wb") as f:
            f.write(d)
    recipe = {"title": "synthetic", "mapper": "plain", "regions": {
        "P": [{"op": "swap16", "files": ["p.bin"]}],
        "C": [{"op": "interleave8", "files": ["c1.bin", "c2.bin"]}],
        "S": [{"files": ["s.bin"]}], "M": [{"files": ["m.bin"]}],
        "V": [{"files": ["v.bin"]}]}}
    # board layout (what the loader accepts) and the canonical variant
    for name, layout in (("synthetic.ngpk", "sdram1"),
                         ("synthetic_canonical.ngpk", "canonical")):
        with open(os.path.join(out, name), "wb") as f:
            f.write(ngpk.pack(recipe, out, layout=layout))


if __name__ == "__main__":
    main(sys.argv[1])
