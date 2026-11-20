#!/usr/bin/env python3
"""Simulates rtl/ng_cfetch.v with Icarus Verilog and checks every pixel
against a model of Geolith's canonical sprite decode.

    python3 -I gateware/tests/test_cfetch.py [region.bin canonical C data]

Without an argument random data is used.  The SDRAM image is the canonical
data converted by tools/ngpk.py (sdram1 layout), so this also checks the
packer permutation against the hardware model.
"""
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tests"))
import ngpk  # noqa: E402

NTILES = 64          # tiles in the simulated C ROM (power of two)
MASK = NTILES - 1


def tpix(c, tile, p, y):
    base = tile * 128 + (((p & 8) ^ 8) << 3) + (y << 2)
    x = p & 7
    v = [c[base + 0] >> x, c[base + 2] >> x, c[base + 1] >> x, c[base + 3] >> x]
    return (v[0] & 1) | (v[1] & 1) << 1 | (v[2] & 1) << 2 | (v[3] & 1) << 3


def run(c_canon, lat, load_delay, nvec=400, seed=5):
    rnd = random.Random(seed)
    sd = ngpk.c_to_sdram1(c_canon)
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "sdram.hex"), "w") as f:
        for i in range(0, len(sd), 4):
            f.write("%08x\n" % int.from_bytes(sd[i:i + 4], "little"))
    vecs = []
    for _ in range(nvec):
        # tile numbers up to 20 bits: the upper bits must fold with the mask
        vecs.append((rnd.randrange(1 << 20), rnd.randrange(16), rnd.randrange(2)))
    with open(os.path.join(d, "vectors.txt"), "w") as f:
        for t, r, h in vecs:
            f.write("%05x %x %d\n" % (t, r, h))
    vvp = os.path.join(d, "sim.vvp")
    subprocess.run(["iverilog", "-g2012", "-o", vvp,
                    "-P", "tb_cfetch.LAT=%d" % lat,
                    "-P", "tb_cfetch.LOAD_DELAY=%d" % load_delay,
                    "-P", "tb_cfetch.MASK=%d" % MASK,
                    os.path.join(HERE, "..", "tb", "tb_cfetch.v"),
                    os.path.join(HERE, "..", "rtl", "ng_cfetch.v")], check=True)
    subprocess.run(["vvp", "-n", vvp], cwd=d, check=True,
                   stdout=subprocess.DEVNULL)
    lines = open(os.path.join(d, "out.txt")).read().split("\n")
    under = int([ln for ln in lines if ln.startswith("UNDERRUN")][0].split()[1])
    # 'x' = the DUT output undefined data (row not fetched in time)
    rows = [tuple(-1 if w == "x" else int(w) for w in ln.split())
            for ln in lines if ln and not ln.startswith("UNDERRUN")]
    return vecs, rows, under


def check(c_canon, lat, load_delay):
    vecs, rows, under = run(c_canon, lat, load_delay)
    assert len(rows) == len(vecs) * 8, (len(rows), len(vecs))
    bad = 0
    it = iter(rows)
    for t, r, h in vecs:
        tile = t & MASK
        for half in range(2):
            pix = []
            for k in range(4):
                _, hv, kk, a, b = next(it)
                assert hv == h and kk == k
                pix += [a, b]
            # model: this half = screen pixels half*8 .. half*8+7, bit x
            exp = [tpix(c_canon, tile, half * 8 + x, r) for x in range(8)]
            if h:
                exp = exp[::-1]
            if pix != exp:
                bad += 1
    return bad, under


def main():
    if len(sys.argv) > 1:
        c = open(sys.argv[1], "rb").read()[:NTILES * 128]
    else:
        c = random.Random(11).randbytes(NTILES * 128)
    ok = True
    # (latency clk, LOAD ticks after PCK1B, must the row be in time?)
    for lat, ld, in_time in ((4, 3, True), (8, 3, True), (8, 1, False)):
        bad, under = check(c, lat, ld)
        print(f"SDRAM latency {lat} clk, LOAD {ld} ticks after PCK1B: "
              f"{bad} wrong half-rows, {under} underruns")
        if in_time and (bad or under):
            ok = False
        if not in_time and not under:
            print("  (expected underruns in this negative test)")
            ok = False
    print("pixel decode: " + ("OK" if ok else "MISMATCH"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
