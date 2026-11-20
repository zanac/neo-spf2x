#!/usr/bin/env python3
"""Census of the Neo Geo cartridges in MAME's software list (hash/neogeo.xml).
Usage: mame_census.py neogeo.xml [--csv out.csv]
For every set: slot type (mapper family), region sizes in bytes and the total.  The totals
are what an .ngpk of that game would need in SDRAM (C is not padded here)."""
import csv, sys, collections
import xml.etree.ElementTree as ET

REG = {"maincpu": "P", "fixed": "S", "audiocpu": "M", "ymsnd:adpcma": "V", "ymsnd:adpcmb": "VB",
       "sprites": "C", "audiocrypt": "MC"}


def census(path):
    out = []
    for sw in ET.parse(path).getroot().iter("software"):
        part = sw.find("part")
        if part is None:
            continue
        slot = next((f.get("value") for f in part.iter("feature") if f.get("name") == "slot"), "rom")
        sizes = collections.Counter()
        for da in part.iter("dataarea"):
            name = da.get("name")
            sizes[REG.get(name, name)] = int(da.get("size"), 0)
        out.append(dict(name=sw.get("name"), desc=(sw.findtext("description") or "").strip(),
                        clone=sw.get("cloneof") or "", slot=slot, **{k: sizes.get(k, 0) for k in
                                                                   ("P", "S", "M", "V", "VB", "C", "MC")}))
    return out


if __name__ == "__main__":
    rows = census(sys.argv[1])
    for r in rows:
        r["total"] = sum(r[k] for k in ("P", "S", "M", "V", "VB", "C"))
    if "--csv" in sys.argv:
        with open(sys.argv[sys.argv.index("--csv") + 1], "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["slot"]].append(r)
    MiB = 1 << 20
    print(f"{len(rows)} sets")
    for s, l in sorted(by.items(), key=lambda x: -len(x[1])):
        print(f"{s:16s} {len(l):4d}  max total {max(x['total'] for x in l)/MiB:6.1f} MiB  e.g. {l[0]['name']}")
    big = sorted(rows, key=lambda r: -r["total"])
    print("largest:", [(r["name"], round(r["total"] / MiB, 1)) for r in big[:12]])
    for lim in (64, 96, 128):
        print(f"> {lim} MiB:", sum(1 for r in rows if r["total"] > lim * MiB))
    print("max P", max(r["P"] for r in rows) / MiB, "V", max(r["V"] for r in rows) / MiB,
          "VB", max(r["VB"] for r in rows) / MiB, "C", max(r["C"] for r in rows) / MiB,
          "S", max(r["S"] for r in rows) / 1024, "KiB M", max(r["M"] for r in rows) / 1024, "KiB")
