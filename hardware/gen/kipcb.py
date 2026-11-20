"""Builds a KiCad 7 PCB from a Design: outline + edge fingers from outline.json, footprints from the
stock libraries and hardware/footprints, collision-free auto placement around anchor parts,
nets assigned.  Routing is done by route.py (freerouting)."""
import json, math, os, shutil
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STOCK = "/usr/share/kicad/footprints"
NGLIB = os.path.join(HW, "footprints", "ng.pretty")


def ng_library():
    """hardware/footprints/ng.pretty: edge fingers + the BGA generated from the Lattice CSV."""
    import fpga_db
    os.makedirs(NGLIB, exist_ok=True)
    for f in os.listdir(os.path.join(HW, "footprints")):
        if f.endswith(".kicad_mod"):
            shutil.copy(os.path.join(HW, "footprints", f), NGLIB)
    open(os.path.join(NGLIB, "BGA-554_26x26_23.0x23.0mm_P0.8mm.kicad_mod"), "w").write(
        fpga_db.footprint(fpga_db.load()))


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    d = NGLIB if lib == "NG" else os.path.join(STOCK, lib + ".pretty")
    fp = pcbnew.FootprintLoad(d, name)
    if fp is None:
        raise RuntimeError("footprint not found: " + fpid)
    return fp


def rect_of(fp):
    """Pad + courtyard bounding box in mm (x0, y0, x1, y1) of a footprint at its current place."""
    x0 = y0 = 1e18
    x1 = y1 = -1e18
    items = list(fp.Pads()) + [g for g in fp.GraphicalItems() if g.GetLayerName() in ("F.CrtYd", "B.CrtYd")]
    for it in items:
        r = it.GetBoundingBox()
        x0, y0 = min(x0, ToMM(r.GetX())), min(y0, ToMM(r.GetY()))
        x1, y1 = max(x1, ToMM(r.GetRight())), max(y1, ToMM(r.GetBottom()))
    return (x0, y0, x1, y1)


class Placer:
    def __init__(self, bounds, keepouts, outline=None):
        self.x0, self.y0, self.x1, self.y1 = bounds
        self.rects = list(keepouts)
        self.outline = outline          # SHAPE_POLY_SET of the real board shape (notches, holes)

    def inside(self, r, inset=0.3):
        if self.outline is None:
            return True
        xm, ym = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        pts = [(r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3]), (xm, r[1]), (xm, r[3]), (r[0], ym), (r[2], ym)]
        for x, y in pts:
            x += -inset if x < xm else inset if x > xm else 0
            y += -inset if y < ym else inset if y > ym else 0
            if not self.outline.Contains(VECTOR2I(FromMM(x), FromMM(y))):
                return False
        return True

    def free(self, r, m=0.35):
        if r[0] < self.x0 + 1 or r[1] < self.y0 + 1 or r[2] > self.x1 - 1 or r[3] > self.y1 - 1:
            return False
        if not self.inside(r):
            return False
        for q in self.rects:
            if r[0] - m < q[2] and r[2] + m > q[0] and r[1] - m < q[3] and r[3] + m > q[1]:
                return False
        return True

    def put(self, fp, cx, cy, step=0.8, rot=0):
        """Moves fp to the free spot nearest (cx, cy), spiral search.  Returns the rect."""
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(FromMM(0), FromMM(0)))
        r0 = rect_of(fp)
        w, h = r0[2] - r0[0], r0[3] - r0[1]
        ox, oy = -(r0[0] + r0[2]) / 2, -(r0[1] + r0[3]) / 2     # centre offset
        for ring in range(0, 400):
            cands = []
            if ring == 0:
                cands = [(0, 0)]
            else:
                for i in range(-ring, ring + 1):
                    cands += [(i, -ring), (i, ring), (-ring, i), (ring, i)]
            cands.sort(key=lambda c: c[0] ** 2 + c[1] ** 2)
            for ix, iy in cands:
                x, y = cx + ix * step, cy + iy * step
                r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                if self.free(r):
                    fp.SetPosition(VECTOR2I(FromMM(x + ox), FromMM(y + oy)))
                    self.rects.append(r)
                    return r
        raise RuntimeError("no room for " + fp.GetReference())


def rules(b):
    """JLCPCB-class 6-layer limits: 0.1/0.1 mm track/space, 0.4/0.2 mm via."""
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(FromMM(1.6))          # 1.6 mm: thickness of the reference cartridge boards
    ds.m_TrackMinWidth = FromMM(0.09)
    ds.m_MinClearance = FromMM(0.09)
    ds.m_ViasMinSize = FromMM(0.4)
    ds.m_MinThroughDrill = FromMM(0.2)
    ds.m_CopperEdgeClearance = FromMM(0.25)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(FromMM(0.1))
    nc.SetTrackWidth(FromMM(0.1))
    nc.SetViaDiameter(FromMM(0.4))
    nc.SetViaDrill(FromMM(0.2))


def planes(b, bounds, nets, fa):
    """GND plane on In1.Cu, +3V3 on In4.Cu (freerouting connects pads to them with vias)."""
    for layer, net in ((pcbnew.In1_Cu, "GND"), (pcbnew.In4_Cu, "+3V3")):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(nets[net])
        z.SetIsFilled(False)
        ol = z.Outline()
        ol.NewOutline()
        x0, y0, x1, y1 = bounds[0] + 0.5, bounds[1] + 0.5, bounds[2] - 0.5, fa["y"] - 6
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(FromMM(x), FromMM(y))
        z.SetMinThickness(FromMM(0.1))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        b.Add(z)
        z.thisown = 0


def build(design, board_key, path, anchors, layers=6):
    """anchors: ref -> (x, y, rot_deg, side)  for the parts with a fixed place.  Everything else is
    placed near the last anchor that precedes it in the design (build order)."""
    ol = json.load(open(os.path.join(HW, "outline.json")))[board_key]
    ng_library()
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(layers)
    # outline
    xs, ys = [], []
    for e in ol["edges"]:
        if e["t"] == "line":
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(VECTOR2I(FromMM(e["x1"]), FromMM(e["y1"])))
            s.SetEnd(VECTOR2I(FromMM(e["x2"]), FromMM(e["y2"])))
            xs += [e["x1"], e["x2"]]; ys += [e["y1"], e["y2"]]
        else:
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_CIRCLE)
            s.SetCenter(VECTOR2I(FromMM(e["cx"]), FromMM(e["cy"])))
            s.SetEnd(VECTOR2I(FromMM(e["cx"] + e["r"]), FromMM(e["cy"])))
            xs += [e["cx"] - e["r"], e["cx"] + e["r"]]; ys += [e["cy"] - e["r"], e["cy"] + e["r"]]
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        b.Add(s)
        s.thisown = 0
    bounds = (min(xs), min(ys), max(xs), max(ys))
    keep = [(e["cx"] - e["r"] - 2, e["cy"] - e["r"] - 2, e["cx"] + e["r"] + 2, e["cy"] + e["r"] + 2)
            for e in ol["edges"] if e["t"] == "circle"]
    # fingers zone keep-out (components stay clear of the contacts' tips)
    fa = ol["fingers"]["A"]
    keep.append((fa["x"] - 64, fa["y"] - 6, fa["x"] + 64, bounds[3]))
    # nets
    nets = {}
    for p in design.parts.values():
        for n in p.pins.values():
            if n and n not in nets:
                ni = pcbnew.NETINFO_ITEM(b, n)
                b.Add(ni)
                ni.thisown = 0
                nets[n] = ni
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline)
    pl = Placer(bounds, keep, outline)
    fps = {}
    last_anchor = None
    for ref, part in design.parts.items():
        fp = load_fp(part.footprint)
        fp.SetReference(ref)
        fp.SetValue(part.value)
        b.Add(fp)
        fp.thisown = 0
        fps[ref] = fp
        for pad in fp.Pads():
            net = part.pins.get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
    # fixed parts first (edge fingers ignore the placer)
    for ref, part in design.parts.items():
        fp = fps[ref]
        if ref in anchors:
            x, y, rot, back = anchors[ref][:4]
            if part.footprint.startswith("NG:neogeo"):
                fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
                if back:
                    fp.Flip(fp.GetPosition(), True)     # mirror about a vertical axis
                if rot:
                    fp.SetOrientationDegrees(rot)
                continue
            if len(anchors[ref]) > 4 and anchors[ref][4]:      # exact place (e.g. flush with the board edge)
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
                pl.rects.append(rect_of(fp))
            else:
                pl.put(fp, x, y, rot=rot)
    # then the rest, near the previous anchor in netlist order
    near = None
    for ref, part in design.parts.items():
        if ref in anchors:
            near = anchors[ref][:2]
            continue
        fp = fps[ref]
        pl.put(fp, near[0], near[1], step=0.9)
    rules(b)
    planes(b, bounds, nets, fa)
    pcbnew.SaveBoard(path, b)
    return b, bounds


# Typical body heights in mm (above the board) used for the shell-fit check.  Estimates from
# memory/datasheets, not measured; the shell clearance itself is NOT known (docs/PCB.md).
HEIGHT = {"BGA-554": 1.6, "TSSOP-48": 1.2, "TSOP-II-54": 1.2, "SOT-223": 1.8, "SOT-23-5": 1.2,
          "SOIC-8W": 2.7, "C_1206": 1.8, "C_0805": 1.4, "C_0603": 0.9, "CP_EIA-3528": 2.1, "L_0603": 0.9, "C_0402": 0.6, "R_0402": 0.5, "L_0805": 1.4,
          "LED_0603": 0.8, "SW_SPST_PTS810": 2.0, "DF12C3.0-80DS": 1.5, "DF12E3.0-80DP": 1.5,
          "PinHeader_2x05": 3.0, "Crystal": 0.9, "microSD": 1.9, "QFN-56": 0.9, "L_Taiyo": 1.8, "PinHeader_1x0": 2.5, "L_": 1.4}
LINK_MATED = 3.0         # mm, Hirose DF12(3.0) mated height (catalogue; excludes solder paste)
HEIGHT_LIMIT = 8.0       # mm, planning value for the whole link stack and any single part


def check_height(design, limit=HEIGHT_LIMIT):
    """Returns (worst part height, link stack height, list of parts over the limit)."""
    def h(fpid):
        for k, v in HEIGHT.items():
            if k in fpid:
                return v
        return None
    over, unknown = [], []
    worst = 0.0
    for ref, p in design.parts.items():
        if p.footprint.startswith("NG:neogeo"):
            continue
        v = h(p.footprint)
        if v is None:
            unknown.append(ref)
            continue
        worst = max(worst, v)
        if v > limit:
            over.append(ref)
    stack = LINK_MATED
    return worst, stack, over, unknown
