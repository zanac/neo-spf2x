"""Generates the Hirose DF12C 80-contact receptacle footprint (the KiCad stock library has the plug
DF12E3.0-80DP and the receptacle only up to 60 contacts).  The geometry is the stock
DF12C3.0-60DS-0.5V pattern extended to 2x40 (same 0.5 mm pitch, pads 0.3 x 1.6 at y = +-1.8 mm,
paste 0.28 x 1.2 at y = +-2.0 mm, numbering 1..40 top row, 41..80 bottom row, left to right).
The body length 22.1 mm is the catalogue value for -80DS (pads span 19.5 mm + 2 x 1.3).
NOT checked against the Hirose engineering drawing (not downloadable here)."""
import os

NAME = "Hirose_DF12_DF12C3.0-80DS-0.5V_2x40_P0.50mm_Vertical"


def footprint():
    n = 40
    x0 = -(n - 1) * 0.25                       # first pad centre, -9.75
    o = []
    o.append(f'(footprint "{NAME}" (version 20211014) (generator ng_hirose_fp)\n  (layer "F.Cu")\n'
             f'  (descr "Hirose DF12C SMD receptacle 80 contacts, extended from the stock DF12C3.0-60DS pattern")\n'
             f'  (tags "connector Hirose DF12 vertical")\n  (attr smd)')
    o.append('  (fp_text reference "REF**" (at 0 -4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    o.append(f'  (fp_text value "{NAME}" (at 0 4) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    o.append('  (fp_text user "${REFERENCE}" (at 0 -1.1) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    hx = x0 - 1.41                              # silk/body half length 11.16
    for a, b_, c, d, l, w in [
        (-hx - 1.0, 1.91, hx - 1.0 + 0.0, 1.91, "F.SilkS", 0.12)]:
        pass
    sx = abs(hx)
    def ln(xa, ya, xb, yb, layer, w):
        o.append(f'  (fp_line (start {xa:.3f} {ya:.3f}) (end {xb:.3f} {yb:.3f}) (layer "{layer}") (width {w}))')
    ln(-sx + 1, 1.91, -sx, 1.91, "F.SilkS", .12); ln(-sx, 1.91, -sx, -1.91, "F.SilkS", .12)
    ln(-sx, -1.91, -sx + 1, -1.91, "F.SilkS", .12); ln(-sx + 1, -1.91, -sx + 1, -2.333, "F.SilkS", .12)
    ln(sx - 1, 1.91, sx, 1.91, "F.SilkS", .12); ln(sx, 1.91, sx, -1.91, "F.SilkS", .12)
    ln(sx, -1.91, sx - 1, -1.91, "F.SilkS", .12)
    cx = 11.55
    for (a, b_, c, d) in [(cx, 3.1, cx, -3.1), (cx, -3.1, -cx, -3.1), (-cx, -3.1, -cx, 3.1), (-cx, 3.1, cx, 3.1)]:
        ln(a, b_, c, d, "F.CrtYd", .05)
    fx = 11.05
    for (a, b_, c, d) in [(-fx, -1.8, fx, -1.8), (fx, -1.8, fx, 1.8), (fx, 1.8, -fx, 1.8), (-fx, 1.8, -fx, -1.8)]:
        ln(a, b_, c, d, "F.Fab", .1)
    for i in range(80):
        row, col = divmod(i, n)
        x = x0 + 0.5 * col
        y = -1.8 if row == 0 else 1.8
        o.append(f'  (pad "{i+1}" smd rect (at {x:.3f} {y}) (size 0.3 1.6) (layers "F.Cu" "F.Mask"))')
        o.append(f'  (pad "" smd rect (at {x:.3f} {2 if row else -2}) (size 0.28 1.2) (layers "F.Paste"))')
    o.append(")")
    return "\n".join(o) + "\n"


def write(libdir):
    open(os.path.join(libdir, NAME + ".kicad_mod"), "w").write(footprint())
