#!/usr/bin/env python3
"""MVS variant: self-checking testbench for ng_cfetch_mvs / ng_mvs_pdec, and an
elaboration check of ng_top with MVS = 0 and MVS = 1.

    python3 -I gateware/tests/test_mvs.py
"""
import glob
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.join(HERE, "..", "rtl")
TB = os.path.join(HERE, "..", "tb")


def main():
    d = tempfile.mkdtemp()
    vvp = os.path.join(d, "m.vvp")
    subprocess.run(["iverilog", "-g2012", "-o", vvp, os.path.join(TB, "tb_mvs.v"),
                    os.path.join(RTL, "ng_cfetch_mvs.v"), os.path.join(RTL, "ng_mvs_pdec.v")], check=True)
    out = subprocess.run(["vvp", "-n", vvp], capture_output=True, text=True, check=True).stdout
    if "TB_MVS PASS" not in out:
        print(out)
        print("FAIL: tb_mvs")
        return 1
    for mvs in (0, 1):
        subprocess.run(["iverilog", "-g2012", "-s", "ng_top", "-P", f"ng_top.MVS={mvs}",
                        "-o", os.path.join(d, f"t{mvs}.vvp")] + sorted(glob.glob(os.path.join(RTL, "*.v"))), check=True)
    print("test_mvs: OK (cfetch_mvs, pdec, ng_top MVS=0/1 elaborate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
