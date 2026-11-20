#!/usr/bin/env python3
"""Extract Edge.Cuts geometry and the edge-finger placement of the reference cartridge boards
(jwestfall69/neogeo-diag-{aes,mvs}-{prog,cha}, public domain) into hardware/outline.json, so the
generated boards keep the real board shape and finger position.  Needs KiCad's python (pcbnew).

    python3 extract_outlines.py AES_PROG.kicad_pcb AES_CHA.kicad_pcb MVS_PROG.kicad_pcb MVS_CHA.kicad_pcb
"""
import json, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 1e6


def one(path):
    b = pcbnew.LoadBoard(path)
    edges = []
    for d in b.GetDrawings():
        if d.GetLayerName() != "Edge.Cuts":
            continue
        s = d.GetShapeStr()
        if s == "Line":
            edges.append(dict(t="line", x1=d.GetStart().x / MM, y1=d.GetStart().y / MM,
                              x2=d.GetEnd().x / MM, y2=d.GetEnd().y / MM))
        elif s == "Circle":
            edges.append(dict(t="circle", cx=d.GetCenter().x / MM, cy=d.GetCenter().y / MM,
                              r=d.GetRadius() / MM))
        else:
            raise SystemExit("unsupported edge shape " + s)
    fingers = {}
    for fp in b.GetFootprints():
        n = str(fp.GetFPID().GetLibItemName())
        if "side-edge" in n:
            side = "A" if "a-side" in n else "B"
            fingers[side] = dict(x=fp.GetPosition().x / MM, y=fp.GetPosition().y / MM,
                                 rot=fp.GetOrientationDegrees(), bottom=fp.IsFlipped())
    return dict(edges=edges, fingers=fingers)


def main(a):
    keys = ["aes_prog", "aes_cha", "mvs_prog", "mvs_cha"]
    out = {k: one(p) for k, p in zip(keys, a[1:5])}
    json.dump(out, open(os.path.join(HERE, "..", "outline.json"), "w"), indent=1)
    for k, v in out.items():
        print(k, len(v["edges"]), v["fingers"])


if __name__ == "__main__":
    main(sys.argv)
