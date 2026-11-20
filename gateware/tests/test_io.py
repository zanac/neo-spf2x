#!/usr/bin/env python3
"""ADPCM buses (ng_adpcm A/B) and the MCU SPI slave (ng_mcu_spi): self-checking testbenches.

    python3 -I gateware/tests/test_io.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.join(HERE, "..", "rtl")
TB = os.path.join(HERE, "..", "tb")


def run(tb, rtl, marker):
    d = tempfile.mkdtemp()
    vvp = os.path.join(d, "t.vvp")
    subprocess.run(["iverilog", "-g2012", "-o", vvp, os.path.join(TB, tb)] +
                   [os.path.join(RTL, r) for r in rtl], check=True)
    out = subprocess.run(["vvp", "-n", vvp], capture_output=True, text=True, check=True).stdout
    if marker + " PASS" not in out:
        print(out)
        print("FAIL:", tb)
        return False
    return True


def main():
    ok = run("tb_adpcm.v", ["ng_adpcm.v", "ng_rdport.v"], "TB_ADPCM")
    ok = run("tb_spi.v", ["ng_mcu_spi.v"], "TB_SPI") and ok
    if not ok:
        return 1
    print("test_io: OK (ADPCM-A/B bus, MCU SPI slave incl. quad write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
