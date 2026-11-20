#!/usr/bin/env python3
"""Simulation tests (Icarus Verilog) for ng_sfetch, ng_pbank and ng_zmc against
Python reference models written from docs/TIMING.md / Geolith behaviour.

    python3 -I gateware/tests/test_modules.py
"""
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.join(HERE, "..", "rtl")
TB = os.path.join(HERE, "..", "tb")
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import ngpk  # noqa: E402


def sim(tbname, rtl, vectors, image=None, params=(), words=65536):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "vectors.txt"), "w") as f:
        f.write(vectors)
    with open(os.path.join(d, "sdram.hex"), "w") as f:
        if image:
            for i in range(0, len(image), 4):
                f.write("%08x\n" % int.from_bytes(image[i:i + 4].ljust(4, b"\0"), "little"))
        else:
            f.write("00000000\n")
    vvp = os.path.join(d, "s.vvp")
    cmd = ["iverilog", "-g2012", "-o", vvp]
    for k, v in params:
        cmd += ["-P", f"{tbname}.{k}={v}"]
    cmd += [os.path.join(TB, tbname + ".v"), os.path.join(TB, "sim_mem.v")]
    cmd += [os.path.join(RTL, r) for r in rtl]
    subprocess.run(cmd, check=True)
    subprocess.run(["vvp", "-n", vvp], cwd=d, check=True, stdout=subprocess.DEVNULL)
    return open(os.path.join(d, "out.txt")).read().split("\n")


# ---------------------------------------------------------------- fix layer
def test_sfetch():
    rnd = random.Random(21)
    ntiles = 64
    canon = rnd.randbytes(ntiles * 32)
    image = ngpk.s_to_sdram1(canon)
    vecs, exp = [], []
    for _ in range(500):
        t, pos = rnd.randrange(1 << 12), rnd.randrange(16)
        vecs.append("%03x %x\n" % (t, pos))
        for s in range(2):
            exp.append(canon[(t & (ntiles - 1)) * 32 + (pos << 1 | s)])
    out = sim("tb_sfetch", ["ng_sfetch.v"], "".join(vecs), image)
    rows = [ln.split() for ln in out if ln and not ln.startswith("TIMEOUT")]
    got = [int(r[2], 16) for r in rows]
    assert out[-2].startswith("TIMEOUT 0"), out[-2:]
    assert got == exp, "fix byte mismatch"
    return len(exp)


# ------------------------------------------------------------------- P bank
def test_pbank():
    rnd = random.Random(33)
    p = bytearray(rnd.randbytes(5 * 1024 * 1024))     # 1 MiB P1 + 4 banks
    mask = 3
    bank = 0
    lines, exp = [], []
    for _ in range(600):
        k = rnd.random()
        if k < 0.15:                                   # latch write in window
            v = rnd.randrange(65536)
            a = 0x200000 + rnd.randrange(0x100000 // 2) * 2
            lines.append("W %06x %04x\n" % (a, v))
            bank = v & mask
        elif k < 0.55:                                 # P1 read
            a = rnd.randrange(0x100000 // 2) * 2
            lines.append("R %06x 0000\n" % a)
            exp.append((int.from_bytes(p[a:a + 2], "big"), 1))
        elif k < 0.95:                                 # window read
            a = 0x200000 + rnd.randrange(0x100000 // 2) * 2
            off = (bank + 1) * 0x100000 + (a & 0xFFFFF)
            lines.append("R %06x 0000\n" % a)
            # banks beyond the loaded data read as zeros in the image
            data = bytes(p[off:off + 2]).ljust(2, b"\0")
            exp.append((int.from_bytes(data, "big"), 1))
        else:                                          # not the cartridge
            a = 0x100000 + rnd.randrange(0x100000 // 2) * 2
            lines.append("R %06x 0000\n" % a)
            exp.append(None)
    # pbank does not answer outside the cart: the testbench times out and
    # prints stale data; drop those expectations and entries
    out = sim("tb_pbank", ["ng_pbank.v"], "".join(lines), bytes(p).ljust(6 << 20, b"\0"))
    rows = [tuple(int(x, 16) if i == 0 else int(x) for i, x in enumerate(ln.split()))
            for ln in out if ln]
    exp_all = exp
    assert len(rows) == len(exp_all), (len(rows), len(exp_all))
    n = 0
    for (d, ic), e in zip(rows, exp_all):
        if e is None:
            assert ic == 0
        else:
            assert (d, ic) == e, (hex(d), e)
            n += 1
    return n


# ------------------------------------------------------------------ Z80 ZMC
def zmc_model():
    n = [2, 6, 14, 30]                 # identity windows at reset
    masks = [0x1F, 0x3F, 0x7F, 0xFF]
    shifts = [14, 13, 12, 11]
    port2win = {3: 0, 2: 1, 1: 2, 0: 3}

    def port(a):
        if (a & 0xFC) == 0x08:
            w = port2win[a & 3]
            n[w] = ((a >> 8) & 0xFF) & masks[w]

    def read(a):
        if a < 0x8000:
            return a, 1
        if a < 0xC000:
            w = 0
        elif a < 0xE000:
            w = 1
        elif a < 0xF000:
            w = 2
        else:
            w = 3
        sz = 1 << shifts[w]
        return n[w] * sz + (a & (sz - 1)), int(a < 0xF800)
    return port, read


def test_zmc():
    rnd = random.Random(44)
    port, read = zmc_model()
    lines, exp = [], []
    # reset state is identity: addresses must map to themselves
    for a in (0x8000, 0xC123, 0xE456, 0xF012, 0xBFFF, 0x7FFF):
        lines.append("R %04x\n" % a)
        exp.append(read(a))
    for _ in range(800):
        if rnd.random() < 0.4:
            a = (rnd.randrange(256) << 8) | (0x08 + rnd.randrange(4))
            lines.append("P %04x\n" % a)
            port(a)
        elif rnd.random() < 0.1:               # other port: no effect
            a = (rnd.randrange(256) << 8) | rnd.choice([0x00, 0x04, 0x0C, 0x18])
            lines.append("P %04x\n" % a)
            port(a)
        else:
            a = rnd.randrange(0x10000)
            lines.append("R %04x\n" % a)
            exp.append(read(a))
    out = sim("tb_zmc", ["ng_zmc.v"], "".join(lines))
    got = [(int(x.split()[0], 16), int(x.split()[1])) for x in out if x]
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        assert g == e, (hex(g[0]), hex(e[0]))
    # identity check from the first six
    for a, (m, _) in zip((0x8000, 0xC123, 0xE456, 0xF012, 0xBFFF, 0x7FFF), got):
        assert m == a, hex(a)
    return len(exp)


def main():
    for name, fn in (("fix layer fetch (ng_sfetch)", test_sfetch),
                     ("P bank latch + read (ng_pbank)", test_pbank),
                     ("Z80 banking (ng_zmc)", test_zmc)):
        print(f"{name}: {fn()} checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
