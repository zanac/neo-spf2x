#!/usr/bin/env python3
"""Extracts the edge-connector pins of the MVS cartridge boards from the KiCad
schematics of jwestfall69/neogeo-diag-mvs-prog and -mvs-cha (public domain),
and writes hardware/mvs_pins.csv.  No hand transcription.

    git clone https://github.com/jwestfall69/neogeo-diag-mvs-prog
    git clone https://github.com/jwestfall69/neogeo-diag-mvs-cha
    python3 -I hardware/extract_kicad_pins.py PROG.kicad_sch CHA.kicad_sch
where CHA.kicad_sch is neo-zmc-board/neogeo-diag-mvs-cha-neo-zmc-board.kicad_sch
"""
import csv, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def block(s, start):
    d = 0
    for i in range(start, len(s)):
        if s[i] == "(":
            d += 1
        elif s[i] == ")":
            d -= 1
            if d == 0:
                return s[start:i + 1]


def pins(path, name):
    s = open(path, encoding="utf-8").read()
    m = re.search(r'\(symbol "%s"' % re.escape(name), s)
    if not m:
        raise SystemExit(f"symbol {name} not found in {path}")
    blk = block(s, m.start())
    out = []
    for pm in re.finditer(r"\(pin \w+ \w+", blk):
        pb = block(blk, pm.start())
        out.append((int(re.search(r'\(number "([^"]*)"', pb).group(1)),
                    re.search(r'\(name "([^"]*)"', pb).group(1)))
    return sorted(out)


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    rows = []
    for board, path in (("PROG", argv[1]), ("CHA", argv[2])):
        for side in ("a", "b"):
            sym = f"neogeo-diag:neogeo-mvs-{board.lower()}-{side}-side-edge"
            for num, nm in pins(path, sym):
                rows.append((board, side.upper(), num, nm))
    with open(os.path.join(HERE, "mvs_pins.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["board", "side", "pin", "signal"])
        w.writerows(rows)
    print(len(rows), "pins written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
