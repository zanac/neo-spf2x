#!/usr/bin/env python3
"""Two-chip SDRAM (ngsd-128M): chip select by addr[26], init/refresh on both chips."""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
d = tempfile.mkdtemp()
open(os.path.join(d, "sdram.hex"), "w").write("00000000\n" * 4)
tb = os.path.join(HERE, "..", "tb")
rtl = os.path.join(HERE, "..", "rtl", "ng_sdram.v")
subprocess.run(["iverilog", "-g2012", "-o", os.path.join(d, "s.vvp"), os.path.join(tb, "tb_sdram2.v"),
                os.path.join(tb, "sim_sdr.v"), rtl], check=True)
out = subprocess.run(["vvp", "-n", os.path.join(d, "s.vvp")], cwd=d, check=True,
                     capture_output=True, text=True).stdout
print(out.strip())
m = re.search(r"errors0=(\d+) errors1=(\d+) bad=(\d+) ref0=(\d+) ref1=(\d+) rd0=(\d+) rd1=(\d+)", out)
ok = m and m.group(1) == m.group(2) == m.group(3) == "0" and int(m.group(4)) > 3 and int(m.group(5)) > 3
print("test_sdram2:", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
