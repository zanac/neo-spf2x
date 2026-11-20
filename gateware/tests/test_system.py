#!/usr/bin/env python3
"""System simulation: ng_top + ng_sdram controller + SDRAM chip model, every
console-side path checked against Python reference models, plus SDRAM protocol
checks done by the chip model (timing, refresh).

    python3 -I gateware/tests/test_system.py
"""
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import ngpk  # noqa: E402
import test_modules as tm  # noqa: E402
import test_cfetch as tc  # noqa: E402

KiB, MiB = 1024, 1 << 20
P_BASE, V_BASE, S_BASE, M_BASE, C_BASE = 0, 0x300000, 0x340000, 0x350000, 0x400000
SIZES = {"P": 3 * MiB, "C": 256 * KiB, "S": 64 * KiB, "M": 256 * KiB, "V": 128 * KiB}
MEM = 8 * MiB


def build():
    rnd = random.Random(2024)
    reg = {k: rnd.randbytes(n) for k, n in SIZES.items()}
    img = bytearray(MEM)
    img[P_BASE:P_BASE + SIZES["P"]] = reg["P"]
    img[V_BASE:V_BASE + SIZES["V"]] = reg["V"]
    img[S_BASE:S_BASE + SIZES["S"]] = ngpk.s_to_sdram1(reg["S"])
    img[M_BASE:M_BASE + SIZES["M"]] = reg["M"]
    img[C_BASE:C_BASE + SIZES["C"]] = ngpk.c_to_sdram1(reg["C"])
    return reg, img


def run_sim(img, cmds, tb="tb_top", extra=()):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "sdram.hex"), "w") as f:
        for i in range(0, len(img), 4):
            f.write("%08x\n" % int.from_bytes(img[i:i + 4], "little"))
    with open(os.path.join(d, "cmds.txt"), "w") as f:
        f.write(cmds)
    rtl = [os.path.join(HERE, "..", "rtl", n) for n in
           ("ng_top.v", "ng_arb.v", "ng_fifo4.v", "ng_sdram.v", "ng_cfetch.v",
            "ng_sfetch.v", "ng_pbank.v", "ng_zmc.v", "ng_rdport.v")]
    tbd = os.path.join(HERE, "..", "tb")
    vvp = os.path.join(d, "s.vvp")
    subprocess.run(["iverilog", "-g2012", "-o", vvp, os.path.join(tbd, tb + ".v"),
                    os.path.join(tbd, "sim_sdr.v")] + rtl + list(extra), check=True)
    p = subprocess.run(["vvp", "-n", vvp], cwd=d, check=True, capture_output=True,
                       text=True)
    out = open(os.path.join(d, "out.txt")).read().split("\n")
    return [ln for ln in out if ln], p.stdout


def main():
    reg, img = build()
    rnd = random.Random(99)
    cmds, exp = [], []
    # --- loader view: program the registers like firmware/ngsd_loader.c
    for t, (sz, base) in {1: (SIZES["P"], P_BASE), 2: (SIZES["C"], C_BASE),
                          3: (SIZES["S"], S_BASE), 4: (SIZES["M"], M_BASE),
                          5: (SIZES["V"], V_BASE)}.items():
        cmds.append("R %02x %08x\n" % (0x10 + t - 1, sz))
        cmds.append("R %02x %08x\n" % (0x20 + t - 1, base))
    cmds.append("R 00 00000001\n")
    # --- MCU write/read-back in a free area
    words = [(0x600000 + 4 * i, rnd.getrandbits(32)) for i in range(16)]
    for a, w in words:
        cmds.append("MW %08x %08x\n" % (a, w))
    for a, w in words:
        cmds.append("MR %08x\n" % a)
        exp.append(("MR", "%x" % w))
    # --- sprites
    c_exp = []
    for _ in range(120):
        t, r_, h = rnd.randrange(1 << 20), rnd.randrange(16), rnd.randrange(2)
        cmds.append("C %05x %x %d\n" % (t, r_, h))
        for half in range(2):
            pix = [tc.tpix(reg["C"], t & 2047, half * 8 + x, r_) for x in range(8)]
            if h:
                pix = pix[::-1]
            c_exp.append(pix)
    # --- fix
    s_exp = []
    for _ in range(150):
        t, pos = rnd.randrange(1 << 12), rnd.randrange(16)
        cmds.append("S %03x %x\n" % (t, pos))
        s_exp.append((reg["S"][(t & 2047) * 32 + (pos << 1)],
                      reg["S"][(t & 2047) * 32 + (pos << 1 | 1)]))
    # --- 68k
    bank = 0
    p_exp = []
    for _ in range(200):
        k = rnd.random()
        if k < 0.15:
            v = (rnd.randrange(1 << 14) << 2) | rnd.randrange(2)
            cmds.append("PW %06x %04x\n" % (0x200000 + rnd.randrange(0x80000) * 2, v))
            bank = v & 3
        else:
            if k < 0.55:
                a = rnd.randrange(0x80000) * 2
                off = a
            else:
                a = 0x200000 + rnd.randrange(0x80000) * 2
                off = (bank + 1) * MiB + (a & 0xFFFFF)
            cmds.append("PR %06x\n" % a)
            p_exp.append(int.from_bytes(reg["P"][off:off + 2], "big"))
    # --- Z80
    port, read = tm.zmc_model()
    z_exp = []
    for _ in range(200):
        if rnd.random() < 0.4:
            a = (rnd.randrange(256) << 8) | (0x08 + rnd.randrange(4))
            cmds.append("ZP %04x\n" % a)
            port(a)
        else:
            a = rnd.randrange(0xF800)
            cmds.append("ZM %04x\n" % a)
            moff, _ = read(a)
            z_exp.append(img[M_BASE + moff])
    # --- V
    v_exp = []
    for _ in range(60):
        o = rnd.randrange(SIZES["V"])
        cmds.append("VR %x\n" % o)
        v_exp.append(img[V_BASE + o])

    out, _ = run_sim(img, "".join(cmds))
    last = out[-1]
    assert last.startswith("SDRAM_ERRORS 0 "), last
    by = {}
    for ln in out[:-1]:
        by.setdefault(ln.split()[0], []).append(ln.split()[1:])
    mr = [("MR", x[0]) for x in by["MR"]]
    assert mr == exp, "MCU write/read-back mismatch"
    px = by["C"]
    assert len(px) == len(c_exp) * 4
    for i, e in enumerate(c_exp):
        got = []
        for k in range(4):
            _, _, _, a, b = px[i * 4 + k]
            got += [int(a, 16), int(b, 16)]
        assert got == e, f"sprite half {i}: {got} != {e}"
    assert [(int(a, 16), int(b, 16)) for a, b in by["S"]] == s_exp, "fix mismatch"
    assert [int(x[0], 16) for x in by["PR"]] == p_exp, "68k read mismatch"
    assert [int(x[0], 16) for x in by["ZM"]] == z_exp, "Z80 M read mismatch"
    assert [int(x[0], 16) for x in by["VR"]] == v_exp, "V read mismatch"
    print("system: MCU r/w %d, sprite halves %d, fix %d, 68k %d, Z80 %d, V %d: OK"
          % (len(mr), len(c_exp), len(s_exp), len(p_exp), len(z_exp), len(v_exp)))
    print("SDRAM chip model:", last)
    return 0


if __name__ == "__main__":
    sys.exit(main())
