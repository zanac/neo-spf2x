#!/usr/bin/env python3
"""Builds hardware/signals.csv from docs/AES_PINOUT.md and prints the I/O budget.

Direction is a GUESS from the signal names (marked in the 'basis' column):
verify with a real cartridge / the wiki 'Signal names' page before layout.
Direction is seen from the cartridge: in = console drives, out = cartridge drives.

    python3 hardware/gen_signals.py > /dev/null   # writes hardware/signals.csv
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "..", "docs", "AES_PINOUT.md")
SKIP = {"GND", "VCC", "L_IN", "L_OUT", "R_IN", "R_OUT", "NC"}


def direction(sig):
    s = sig
    if re.fullmatch(r"D\d+", s) or re.fullmatch(r"SDD\d", s):
        return "bidir", "data bus (read by console, write for bank latch / Z80 bus)"
    if re.fullmatch(r"SD(PAD|RAD)\d", s):
        return "bidir", "ADPCM multiplexed address/data bus"
    if re.fullmatch(r"CR\d+", s):
        return "out", "MVS: 32-bit parallel C ROM data towards the console"
    if s in ("DOTA", "DOTB") or re.fullmatch(r"(GAD|GBD|FIXD)\d", s):
        return "out", "pixel / fix data towards the console"
    if s in ("ROMWAIT", "PWAIT0", "PWAIT1", "PDTACK"):
        return "out", "wait lines towards the console (docs/BOOT.md)"
    if s == "4MB":
        return "unknown", "strap/size pin, function unverified"
    return "in", "address / strobe / clock / bank bits driven by the console"


def mvs():
    """MVS: pins come from hardware/mvs_pins.csv (extract_kicad_pins.py)."""
    rows = []
    with open(os.path.join(HERE, "mvs_pins.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["signal"] in SKIP:
                continue
            d, basis = direction(r["signal"])
            rows.append((r["board"], r["side"], int(r["pin"]), r["signal"], d, basis))
    with open(os.path.join(HERE, "signals_mvs.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["board", "side", "pin", "signal", "dir_guess", "basis"])
        w.writerows(rows)
    uniq = {r[3] for r in rows}
    print("MVS console-side pins:", len(rows), "unique signals:", len(uniq))
    by = {}
    for r in rows:
        by[r[4]] = by.get(r[4], 0) + 1
    for d, n in sorted(by.items()):
        print(f"  {d:8} {n:3}")


def main():
    text = open(DOC, encoding="utf-8").read()
    rows = []
    for sec in re.split(r"^## ", text, flags=re.M):
        title = sec.split("\n")[0]
        if not title.startswith("Scheda"):
            continue
        board = title.split()[1]
        for ln in sec.split("\n"):
            m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", ln)
            if not m:
                continue
            for side, sig in (("A", m.group(2)), ("B", m.group(3))):
                if sig in SKIP:
                    continue
                d, basis = direction(sig)
                rows.append((board, side, int(m.group(1)), sig, d, basis))
    path = os.path.join(HERE, "signals.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["board", "side", "pin", "signal", "dir_guess", "basis"])
        w.writerows(rows)
    by = {}
    for r in rows:
        by.setdefault(r[4], []).append(r[3])
    print("console-side signals needing a 5 V <-> 3.3 V path:", len(rows))
    for d, l in sorted(by.items()):
        print(f"  {d:8} {len(l):3}")
    mvs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
