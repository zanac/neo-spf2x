#!/usr/bin/env python3
"""Runs the worst-case traffic of docs/GATEWARE.md on the RTL chain
(ng_top + ng_sdram + chip model) and prints request->ready latencies.

    python3 -I gateware/model/rtl_budget.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..")
RTL = [os.path.join(G, "rtl", n) for n in
       ("ng_top.v", "ng_arb.v", "ng_fifo4.v", "ng_sdram.v", "ng_cfetch.v",
        "ng_sfetch.v", "ng_pbank.v", "ng_zmc.v", "ng_rdport.v", "ng_boot.v")]

CONFIGS = {   # name: parameters (clock period ns, cycles per 12M, timings in clk)
    "96 MHz":  dict(PERIOD=10.4167, DIV12=8, TRCD=2, CL=3, TRC=7, TRP=2, TRFC=7, REFI=740),
    "144 MHz": dict(PERIOD=6.9444, DIV12=12, TRCD=3, CL=3, TRC=10, TRP=3, TRFC=10, REFI=1100),
}


def run(name, p):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "sdram.hex"), "w") as f:
        f.write("00000000\n")
    vvp = os.path.join(d, "s.vvp")
    cmd = ["iverilog", "-g2012", "-o", vvp]
    for k, v in p.items():
        cmd += ["-P", f"tb_stress.{k}={v}"]
    cmd += [os.path.join(G, "tb", "tb_stress.v"), os.path.join(G, "tb", "sim_sdr.v")] + RTL
    subprocess.run(cmd, check=True)
    out = subprocess.run(["vvp", "-n", vvp], cwd=d, check=True, capture_output=True,
                         text=True).stdout
    vals = {}
    for ln in out.splitlines():
        w = ln.split()
        if w and w[0] in ("C_HALF0_MAX", "C_ROW_MAX", "C_ROW_AVG", "S_MAX", "P_MAX",
                          "M_MAX", "V_MAX"):
            vals[w[0]] = float(w[1])
        elif ln.startswith("SDRAM_ERRORS"):
            vals["err"] = int(w[1])
        elif ln.startswith("EVENTS"):
            vals["events"] = ln
    return vals, out


def main():
    ok = True
    for name, p in CONFIGS.items():
        v, out = run(name, p)
        print(f"{name}: C half0 {v['C_HALF0_MAX']:.0f} ns, C row (both halves) "
              f"max {v['C_ROW_MAX']:.0f} / avg {v['C_ROW_AVG']:.0f} ns, "
              f"S {v['S_MAX']:.0f}, P {v['P_MAX']:.0f}, M {v['M_MAX']:.0f}, "
              f"V {v['V_MAX']:.0f} ns; SDRAM protocol errors {v['err']}")
        print("   ", v["events"])
        if v["err"]:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
