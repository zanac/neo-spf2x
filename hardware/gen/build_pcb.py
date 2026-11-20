"""Places the CHA board of one format (aes|mvs): python3 build_pcb.py aes  -> out/<fmt>_cha.kicad_pcb"""
import json, os, sys
import boards, kipcb

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")


def cha_anchors(fmt, d):
    ol = json.load(open(os.path.join(kipcb.HW, "outline.json")))[f"{fmt}_cha"]
    fa, fb = ol["fingers"]["A"], ol["fingers"]["B"]
    cx = fa["x"]
    a = {}
    refs = list(d.parts)
    byval = lambda s: [r for r in refs if d.parts[r].value.startswith(s)]
    fpga = byval("LFE5U")[0]
    a[fpga] = (cx, 85, 0, False)
    sd = byval("AS4C32M16SB")
    a[sd[0]] = (98, 66, 0, False)
    a[sd[1]] = (98, 102, 0, False)
    a[byval("W25Q128")[0]] = (cx - 24, 108, 0, False)
    for i, r in enumerate(byval("TLV62569")):
        a[r] = (176 + 14 * i, 36, 0, False)
    a[byval("2.2uH")[0]] = (222, 36, 0, False)
    tr = byval("SN74ALVC")
    n = len(tr)
    pitch = 11.5
    x0 = cx - pitch * (n - 1) / 2
    for i, r in enumerate(tr):
        a[r] = (x0 + i * pitch, 137, 0, False)
    j_edge = [r for r in refs if d.parts[r].footprint.startswith("NG:neogeo")]
    a[j_edge[0]] = (fa["x"], fa["y"], fa["rot"], False)
    a[j_edge[1]] = (fb["x"], fb["y"], fb["rot"], True)
    links = [r for r in refs if d.parts[r].value.startswith("LINK")]
    a[links[0]] = (212, 85, 90, False)
    a[links[1]] = (224, 85, 90, False)
    a[byval("JTAG")[0]] = (cx - 36, 122, 0, False)
    a[byval("DONE")[0]] = (80, 135, 0, False)
    a[byval("PROGRAMN")[0]] = (80, 146, 0, False)
    return a


def prog_anchors(fmt, d):
    ol = json.load(open(os.path.join(kipcb.HW, "outline.json")))[f"{fmt}_prog"]
    fa, fb = ol["fingers"]["A"], ol["fingers"]["B"]
    cx = fa["x"]
    a = {}
    refs = list(d.parts)
    byval = lambda s: [r for r in refs if d.parts[r].value.startswith(s)]
    a[byval("RP2040")[0]] = (cx - 8, 85, 0, False)
    a[byval("W25Q128")[0]] = (cx - 30, 100, 0, False)
    a[byval("12MHz")[0]] = (cx - 30, 78, 0, False)
    # Hirose DM3AT footprint: contacts at -y, the card enters from +y.  Rot 180 makes the slot open
    # towards the top edge of the board (the edge opposite the fingers), which stays reachable.
    # Courtyard edge flush with the top edge of the board (y = 23.75 mm): the card is inserted from the
    # top edge of the cartridge.  Exact placement (the placer would keep it 0.3 mm inside).
    a[byval("microSD")[0]] = (cx + 6, 23.75 + 8.35, 180, False, True)
    tr = byval("SN74ALVC")
    n = len(tr)
    pitch = 11.5
    x0 = cx - pitch * (n - 1) / 2
    for i, r in enumerate(tr):
        a[r] = (x0 + i * pitch, 137, 0, False)
    j_edge = [r for r in refs if d.parts[r].footprint.startswith("NG:neogeo")]
    a[j_edge[0]] = (fa["x"], fa["y"], fa["rot"], False)
    a[j_edge[1]] = (fb["x"], fb["y"], fb["rot"], True)
    # PROG and CHA outlines come from different reference drawings with their own origin.
    links = [r for r in refs if d.parts[r].value.startswith("LINK")]
    # PROG is flipped about a vertical axis onto CHA.  Registration: the bounding boxes of the two
    # outlines coincide after the flip (x mirrored about the box centre, bottom edges aligned); the
    # mirrored outlines differ by < 1 % of the area (60-180 mm2 of 22000, measured).
    oj = json.load(open(os.path.join(kipcb.HW, "outline.json")))
    def box(k):
        xs = [v for e in oj[k]["edges"] if e["t"] == "line" for v in (e["x1"], e["x2"])]
        ys = [v for e in oj[k]["edges"] if e["t"] == "line" for v in (e["y1"], e["y2"])]
        return min(xs), min(ys), max(xs), max(ys)
    cx0, cy0, cx1, cy1 = box(f"{fmt}_cha")
    px0, py0, px1, py1 = box(f"{fmt}_prog")
    xm = (cx0 + cx1) / 2 + (px0 + px1) / 2          # CHA x = xm - PROG x
    dy = cy1 - py1                                  # CHA y = PROG y + dy
    # LINK1 / LINK2 sit at x = 212 / 224 and y = 85 on CHA (plugs rotated 90, like the receptacles)
    a[links[0]] = (xm - 212, 85 - dy, 90, False)
    a[links[1]] = (xm - 224, 85 - dy, 90, False)
    a[byval("USB/SWD")[0]] = (cx - 50, 60, 0, False)
    a[byval("SWD")[0]] = (cx - 50, 72, 0, False)
    a[byval("RESET")[0]] = (80, 135, 0, False)
    a[byval("BOOTSEL")[0]] = (80, 146, 0, False)
    a[byval("MCU")[0]] = (80, 125, 0, False)
    return a


def main_prog(fmt):
    d = boards.build_prog(fmt)
    path = os.path.join(OUT, f"{fmt}_prog.kicad_pcb")
    b, bounds = kipcb.build(d, f"{fmt}_prog", path, prog_anchors(fmt, d))
    w, st, over, unk = kipcb.check_height(d)
    print(f"{fmt} prog placed", len(d.parts), "parts ->", path, "bounds", bounds, "height", w, over, unk)


def main(fmt):
    d, assign = boards.build_cha(fmt)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{fmt}_cha.kicad_pcb")
    b, bounds = kipcb.build(d, f"{fmt}_cha", path, cha_anchors(fmt, d))
    import pcbnew, fanout
    brd = pcbnew.LoadBoard(path)
    print("BGA fanout vias:", fanout.fanout(brd))
    pcbnew.SaveBoard(path, brd)
    w, st, over, unk = kipcb.check_height(d)
    print(f"height check: tallest part {w} mm, link stack {st} mm (limit {kipcb.HEIGHT_LIMIT}); over: {over}; unknown: {unk}")
    print(fmt, "placed", len(d.parts), "parts ->", path, "bounds", bounds)


if __name__ == "__main__":
    fmt = sys.argv[1] if len(sys.argv) > 1 else "aes"
    if len(sys.argv) > 2 and sys.argv[2] == "prog":
        main_prog(fmt)
    else:
        main(fmt)
