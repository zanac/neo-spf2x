"""LFE5U-45F caBGA554 ball database (from the official Lattice CSV) and footprint generator."""
import csv, os, re

CSV = os.path.join(os.path.dirname(__file__), "..", "fpga",
                   "FPGA-SC-02034-3-0-ECP5U-45-Pinout.csv")
PITCH = 0.8
LETTERS = "ABCDEFGHJKLMNPRTUVWY"       # JEDEC: no I O Q S X Z
LETTERS = list("ABCDEFGHJKLMNPRTUVWY") + ["AA", "AB", "AC", "AD", "AE", "AF"]


def load():
    """-> dict ball -> dict(func, bank, dual, kind) ; kind in gpio/power/gnd/cfg/other"""
    balls = {}
    rows = list(csv.reader(open(CSV, encoding="utf-8", errors="replace")))
    hdr = next(i for i, r in enumerate(rows) if r and r[0] == "PAD")
    col = rows[hdr].index("CABGA554")
    for r in rows[hdr + 1:]:
        if len(r) <= col or r[col] in ("-", ""):
            continue
        f = r[1]
        if re.match(r"^P[LRTB]\d+[A-D]$", f):
            kind = "gpio"
        elif f.startswith("VCCIO"):
            kind = "vccio"
        elif f in ("VCC", "VCCAUX", "VCCA0", "VCCA1", "VCCHRX0", "VCCHTX0", "VCCAUXA0", "VCCAUXA1") or f.startswith("VCC"):
            kind = "power"
        elif f.startswith("VSS") or f.startswith("GND"):
            kind = "gnd"
        else:
            kind = "other"
        balls[r[col]] = dict(func=f, bank=r[2], dual=r[3], kind=kind)
    return balls


def pos(ball):
    m = re.match(r"^([A-Z]+)(\d+)$", ball)
    return LETTERS.index(m.group(1)), int(m.group(2)) - 1


def footprint(balls, name="BGA-554_26x26_23.0x23.0mm_P0.8mm"):
    """Pad coords centred; row letter -> y (A at top), column number -> x."""
    n = 26
    out = [f'(footprint "{name}" (version 20221018) (generator ngsd_gen) (layer "F.Cu")',
           '  (attr smd)',
           '  (fp_text reference "REF**" (at 0 -12.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
           f'  (fp_text value "{name}" (at 0 12.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
           '  (fp_rect (start -11.5 -11.5) (end 11.5 11.5) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS"))',
           '  (fp_rect (start -11.75 -11.75) (end 11.75 11.75) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))']
    for b in sorted(balls, key=lambda b: pos(b)):
        r, c = pos(b)
        x = (c - (n - 1) / 2) * PITCH
        y = (r - (n - 1) / 2) * PITCH
        out.append(f'  (pad "{b}" smd circle (at {x:.3f} {y:.3f}) (size 0.4 0.4) '
                   '(layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))')
    out.append(")")
    return "\n".join(out)


if __name__ == "__main__":
    b = load()
    from collections import Counter
    print(len(b), Counter(v["kind"] for v in b.values()))
    rs = {pos(x)[0] for x in b}; cs = {pos(x)[1] for x in b}
    print(max(rs), max(cs))
    open("/tmp/fpga554.kicad_mod", "w").write(footprint(b))
