"""Geometry checks on a placed board: every part inside the outline, clear of the 5 mm mounting
holes, and (for the link pair) PROG and CHA connectors at the same physical spot.
    python3 checks.py aes_cha aes_prog ..."""
import json, math, os, sys
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kipcb

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
HW = os.path.join(OUT, "..")
mm = lambda v: pcbnew.ToMM(v)
HOLE_MARGIN = 0.5


def check(name):
    b = pcbnew.LoadBoard(os.path.join(OUT, name + ".kicad_pcb"))
    holes = [(mm(d.GetCenter().x), mm(d.GetCenter().y), mm(d.GetRadius())) for d in b.GetDrawings()
             if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_CIRCLE]
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps)
    bad = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("J") and "edge" in str(fp.GetFPID().GetLibItemName()).lower():
            continue                                    # edge fingers sit on the outline by design
        x0, y0, x1, y1 = kipcb.rect_of(fp)             # pads + courtyard (a card sticking out is fine)
        for (hx, hy, r) in holes:
            dx = max(x0 - hx, 0, hx - x1); dy = max(y0 - hy, 0, hy - y1)
            if math.hypot(dx, dy) < r + HOLE_MARGIN:
                bad.append(f"{ref} too close to hole ({hx:.1f},{hy:.1f})")
        for (x, y) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            if not ps.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))):
                bad.append(f"{ref} outside the outline at ({x:.1f},{y:.1f})")
                break
    return holes, bad


def _fp_height(fp):
    fid = str(fp.GetFPID().GetLibItemName())
    for k, v in kipcb.HEIGHT.items():
        if k in fid:
            return v
    return None


def link_mating(cha, prog):
    """PROG is flipped about a vertical axis onto CHA.  The axis is fixed by the connector centres:
    PROG x -> xm - x.  Every PROG link pad must land on the CHA pad with the same number, and parts
    of the two facing sides must not collide (sum of heights below the mated height - 0.3 mm)."""
    bc = pcbnew.LoadBoard(os.path.join(OUT, cha + ".kicad_pcb"))
    bp = pcbnew.LoadBoard(os.path.join(OUT, prog + ".kicad_pcb"))
    def links(b):
        return {fp.GetValue(): fp for fp in b.GetFootprints() if fp.GetValue().startswith("LINK")}
    lc, lp = links(bc), links(bp)
    xm = None
    msgs = []
    for name in lc:
        c = lc[name]
        p = lp[name]
        # PROG pad -> CHA frame: x' = xm - x, y' = y + dy
        if xm is None:
            xm = mm(c.GetPosition().x) + mm(p.GetPosition().x)
            dy = mm(c.GetPosition().y) - mm(p.GetPosition().y)
        cp = {q.GetNumber(): q for q in c.Pads() if q.GetNumber().isdigit()}
        pp = {q.GetNumber(): q for q in p.Pads() if q.GetNumber().isdigit()}
        worst = 0.0
        for k, q in pp.items():
            x = xm - mm(q.GetPosition().x)
            y = mm(q.GetPosition().y) + dy
            worst = max(worst, abs(x - mm(cp[k].GetPosition().x)) + abs(y - mm(cp[k].GetPosition().y)))
            if cp[k].GetNetname() != q.GetNetname():
                msgs.append(f"{name} pad {k}: net {cp[k].GetNetname()} vs {q.GetNetname()}")
        if worst > 0.01:
            msgs.append(f"{name}: pads off by {worst:.3f} mm after the flip")
    hc = sorted((round(mm(d.GetCenter().x), 2), round(mm(d.GetCenter().y), 2)) for d in bc.GetDrawings()
                if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_CIRCLE)
    hp = sorted((round(xm - mm(d.GetCenter().x), 2), round(mm(d.GetCenter().y) + dy, 2)) for d in bp.GetDrawings()
                if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_CIRCLE)
    if len(hc) != len(hp) or any(abs(a[0] - b[0]) > 0.05 or abs(a[1] - b[1]) > 0.05 for a, b in zip(hc, hp)):
        msgs.append(f"mounting holes do not coincide after the flip: CHA {hc} PROG {hp}")
    limit = kipcb.LINK_MATED - 0.3
    boxes = []
    for fp in bp.GetFootprints():
        h = _fp_height(fp)
        if h is None or fp.GetReference().startswith("J") and "edge" in str(fp.GetFPID().GetLibItemName()).lower():
            continue
        if fp.GetValue().startswith("LINK"):
            continue
        x0, y0, x1, y1 = kipcb.rect_of(fp)
        boxes.append((fp.GetReference(), h, xm - x1, y0 + dy, xm - x0, y1 + dy))
    for fp in bc.GetFootprints():
        h = _fp_height(fp)
        if h is None or fp.GetValue().startswith("LINK") or "edge" in str(fp.GetFPID().GetLibItemName()).lower():
            continue
        x0, y0, x1, y1 = kipcb.rect_of(fp)
        for (r, hp, a0, b0, a1, b1) in boxes:
            if a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1 and h + hp > limit:
                msgs.append(f"facing parts {fp.GetReference()} ({h} mm) / PROG {r} ({hp} mm) over {limit:.1f} mm")
    return msgs


if __name__ == "__main__":
    rc = 0
    for n in sys.argv[1:]:
        holes, bad = check(n)
        print(f"{n}: {len(holes)} holes, {len(bad)} geometry problems")
        for m in bad:
            print("   ", m)
        rc |= bool(bad)
    for f in ("aes", "mvs"):
        if f + "_cha" in sys.argv[1:] and f + "_prog" in sys.argv[1:]:
            m = link_mating(f + "_cha", f + "_prog")
            print(f"{f} link mating/clearance: {len(m)} problems")
            for x in m[:40]:
                print("   ", x)
            rc |= bool(m)
    sys.exit(rc)
