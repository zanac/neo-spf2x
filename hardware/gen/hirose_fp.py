"""Generates the Hirose DF12NB(3.0) 80-contact footprints (receptacle -80DS, plug -80DP).
Source: Hirose engineering drawings EDC-390680-51-77 (DS) and EDC-390679-51-77 (DP), recommended
land pattern: signal pads 0.3 x 1.6 mm, pitch 0.5, rows 2.0 mm apart between the pad edges (centres at
y = +-1.8), span B = 19.5; two metal-fitting pads 0.8 x 1.8 mm on the centre line, the gap between them is
A = 22.1 (DS) / 22.2 (DP).  Paste (120 um stencil): signal 0.28 x 1.2 at y = +-2.0, fittings as the pads.
The pad NUMBERING is not on those drawings: it follows the KiCad stock library (receptacle 1..40 top row
left to right and 41..80 bottom row; plug 1..40 bottom row and 41..80 top row), which is what makes plug
and receptacle pin n meet when the PROG board is flipped (checked in checks.py)."""
import os

DS = "Hirose_DF12NB3.0-80DS-0.5V51_2x40_P0.50mm_Vertical"
DP = "Hirose_DF12NB3.0-80DP-0.5V51_2x40_P0.50mm_Vertical"
NAMES = {"DS": DS, "DP": DP}


def footprint(kind):
    name = NAMES[kind]
    a_gap = 22.1 if kind == "DS" else 22.2
    n = 40
    x0 = -(n - 1) * 0.25                       # -9.75
    o = [f'(footprint "{name}" (version 20211014) (generator ng_hirose_fp)\n  (layer "F.Cu")\n'
         f'  (descr "Hirose DF12NB(3.0)-80{kind}-0.5V(51), from the Hirose land pattern drawing")\n'
         f'  (tags "connector Hirose DF12 vertical")\n  (attr smd)']
    o.append('  (fp_text reference "REF**" (at 0 -4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    o.append(f'  (fp_text value "{name}" (at 0 4) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    o.append('  (fp_text user "${REFERENCE}" (at 0 -1.1) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')

    def ln(xa, ya, xb, yb, layer, w):
        o.append(f'  (fp_line (start {xa:.3f} {ya:.3f}) (end {xb:.3f} {yb:.3f}) (layer "{layer}") (width {w}))')
    body = a_gap / 2                            # body half length 11.05 / 11.1
    for (a, b, c, d) in [(-body, -2.3, body, -2.3), (body, -2.3, body, 2.3), (body, 2.3, -body, 2.3), (-body, 2.3, -body, -2.3)]:
        ln(a, b, c, d, "F.Fab", 0.1)
    cx = a_gap / 2 + 0.8 + 0.4                  # courtyard beyond the fitting pads
    for (a, b, c, d) in [(cx, 3.1, cx, -3.1), (cx, -3.1, -cx, -3.1), (-cx, -3.1, -cx, 3.1), (-cx, 3.1, cx, 3.1)]:
        ln(a, b, c, d, "F.CrtYd", 0.05)
    # pin 1 mark on the silk, outside the pad rows
    first_row_y = -1.8 if kind == "DS" else 1.8
    o.append(f'  (fp_circle (center {x0 - 1.0:.3f} {first_row_y * 1.9:.3f}) (end {x0 - 0.8:.3f} {first_row_y * 1.9:.3f}) (layer "F.SilkS") (width 0.12) (fill solid))')
    for i in range(80):
        row, col = divmod(i, n)
        x = x0 + 0.5 * col
        if kind == "DS":
            y = -1.8 if row == 0 else 1.8
        else:
            y = 1.8 if row == 0 else -1.8
        o.append(f'  (pad "{i+1}" smd rect (at {x:.3f} {y}) (size 0.3 1.6) (layers "F.Cu" "F.Mask"))')
        o.append(f'  (pad "" smd rect (at {x:.3f} {2.0 if y > 0 else -2.0}) (size 0.28 1.2) (layers "F.Paste"))')
    fx = a_gap / 2 + 0.4
    for sx in (-1, 1):
        o.append(f'  (pad "MP" smd rect (at {sx * fx:.3f} 0) (size 0.8 1.8) (layers "F.Cu" "F.Mask" "F.Paste"))')
    o.append(")")
    return "\n".join(o) + "\n"


def write(libdir):
    for k, nm in NAMES.items():
        open(os.path.join(libdir, nm + ".kicad_mod"), "w").write(footprint(k))
