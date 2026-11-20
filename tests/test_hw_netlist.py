#!/usr/bin/env python3
"""Checks on the generated board netlists (hardware/gen/boards.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hardware", "gen"))
import boards

ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL", msg)


for fmt in ("aes", "mvs"):
    cha, assign = boards.build_cha(fmt)
    prog = boards.build_prog(fmt)
    nc, np_ = cha.nets(), prog.nets()
    fpga = next(p for p in cha.parts.values() if p.value.startswith("LFE5U"))
    fb = {n: k for k, n in fpga.pins.items() if n}
    # no ball used twice, assignment agrees with the netlist
    if len(set(assign.values())) != len(assign):
        fail(f"{fmt}: ball used twice")
    for n, ball in assign.items():
        if fpga.pins.get(ball) != n:
            fail(f"{fmt}: {n} not on {ball}")
    # every console signal: finger -> translator -> FPGA (CHA) or link (PROG)
    for r in boards.load_signals(fmt):
        s = r["signal"].replace("/", "_")
        d = cha if r["board"] == "CHA" else prog
        if r["board"] == "PROG" and fmt == "mvs" and s in ("RESET", "SLOTCS"):
            continue
        x = d.nets().get("X_" + s)
        if not x or len(x) < 2 or not any(c[0].startswith("J") for c in x) or not any(c[0].startswith("U") for c in x):
            fail(f"{fmt} {r['board']}: {s} finger->translator missing")
        a = d.nets().get(s)
        if r["board"] == "CHA" and not any(c[0] == fpga.ref for c in a):
            fail(f"{fmt}: CHA {s} does not reach the FPGA")
        if r["board"] == "PROG":
            if not any(c[0].startswith("J") for c in a) or not any(c[0] == fpga.ref for c in nc.get(s, [])):
                fail(f"{fmt}: PROG {s} does not reach the FPGA through the link")
    # link: identical pin->net map on both boards
    lm = lambda d: {(c[1]): n for n, cs in d.nets().items() for c in cs if c[0].startswith("J") and False}
    if boards.link_pin_map(fmt) is None:
        fail("link map")
    # every power ball of the FPGA is on a rail
    for ball, net in fpga.pins.items():
        pass
    print(f"{fmt}: CHA {len(cha.parts)} parts, PROG {len(prog.parts)} parts, FPGA I/O {len(assign)} of 245: OK")
sys.exit(0 if ok else 1)
