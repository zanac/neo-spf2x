#!/usr/bin/env python3
"""ngpk - packer / inspector for NGPK (Neo Geo Pack) game containers.

A .ngpk file holds every ROM region of one game in a canonical, hardware
independent byte order, so the cartridge firmware can stream it to SDRAM
without knowing anything about the individual game.  See docs/FORMAT.md.

Usage:
    ngpk.py pack   recipe.json -o game.ngpk
    ngpk.py info   game.ngpk
    ngpk.py verify game.ngpk
    ngpk.py unpack game.ngpk -o outdir
"""
import argparse
import json
import os
import struct
import sys
import zlib

MAGIC = b"NGPK"
VERSION = 1
HDR_SIZE = 64
ENT_SIZE = 32
SECTOR = 512

# <magic, version, hdr_size, flags, nregions, mapper, mapper_arg, ngh, rsvd16,
#  title[32], hdr_crc, rsvd32>
HDR_FMT = "<4sHHIIHHHH32sII"
# <type, flags, rsvd16, size, file_off, crc32, rsvd[16]>
ENT_FMT = "<BBHIII16s"
assert struct.calcsize(HDR_FMT) == HDR_SIZE
assert struct.calcsize(ENT_FMT) == ENT_SIZE

REGION_ID = {"P": 1, "C": 2, "S": 3, "M": 4, "V": 5, "VB": 6}
REGION_NAME = {v: k for k, v in REGION_ID.items()}
# order in which regions are stored in the file: small ones first, C last
STORE_ORDER = ["P", "S", "M", "V", "VB", "C"]
MAPPER_ID = {"plain": 0}
MAPPER_NAME = {v: k for k, v in MAPPER_ID.items()}

TILE_BYTES = 128  # 16x16 px, 4 bpp (wiki: Sprite graphics format)


class PackError(Exception):
    pass


def align(n, a=SECTOR):
    return (n + a - 1) // a * a


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


# ---------------------------------------------------------------- operations
def swap16(data):
    if len(data) % 2:
        raise PackError("swap16: odd file size")
    out = bytearray(len(data))
    out[0::2] = data[1::2]
    out[1::2] = data[0::2]
    return bytes(out)


def interleave8(even, odd):
    if len(even) != len(odd):
        raise PackError("interleave8: the two files differ in size "
                        f"({len(even)} vs {len(odd)})")
    out = bytearray(len(even) * 2)
    out[0::2] = even
    out[1::2] = odd
    return bytes(out)


def build_segment(seg, base_dir):
    files = seg.get("files")
    if not files:
        raise PackError("segment without 'files'")
    op = seg.get("op", "concat")

    def rd(name):
        path = os.path.join(base_dir, name)
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            raise PackError(f"cannot read {path}: {e.strerror}")

    if op == "concat":
        return b"".join(rd(n) for n in files)
    if op == "swap16":
        return b"".join(swap16(rd(n)) for n in files)
    if op == "interleave8":
        if len(files) != 2:
            raise PackError("interleave8 needs exactly 2 files [even, odd]")
        return interleave8(rd(files[0]), rd(files[1]))
    raise PackError(f"unknown op '{op}'")


def build_regions(recipe, base_dir):
    regions = {}
    for name, segs in recipe["regions"].items():
        if name not in REGION_ID:
            raise PackError(f"unknown region '{name}'")
        regions[name] = b"".join(build_segment(s, base_dir) for s in segs)
    return regions


def check_regions(regions, no_check=False):
    if "P" not in regions:
        raise PackError("a game needs a P region")
    if "C" not in regions:
        raise PackError("a game needs a C region")
    p = regions["P"]
    if not no_check and p[0x100:0x107] != b"NEO-GEO":
        raise PackError(
            "P region has no 'NEO-GEO' signature at 0x100 (68k byte order). "
            "Wrong byte swap? use --no-check to override")
    if len(regions["C"]) % TILE_BYTES:
        raise PackError("C region size is not a multiple of 128 bytes "
                        "(one 16x16 tile)")


# --------------------------------------------------------------- container
def pack(recipe, base_dir, no_check=False):
    mapper = recipe.get("mapper", "plain")
    if mapper not in MAPPER_ID:
        raise PackError(f"unsupported mapper '{mapper}' "
                        f"(known: {', '.join(MAPPER_ID)})")
    regions = build_regions(recipe, base_dir)
    check_regions(regions, no_check)

    names = [n for n in STORE_ORDER if n in regions]
    table_end = HDR_SIZE + ENT_SIZE * len(names)
    off = align(table_end)
    entries = []
    blobs = []
    for n in names:
        data = regions[n]
        entries.append(struct.pack(ENT_FMT, REGION_ID[n], 0, 0, len(data),
                                   off, crc32(data), bytes(16)))
        padded = data + bytes(align(len(data)) - len(data))
        blobs.append(padded)
        off += len(padded)
    table = b"".join(entries)

    title = recipe.get("title", "").encode("utf-8")[:31]
    hdr0 = struct.pack(HDR_FMT, MAGIC, VERSION, HDR_SIZE, 0, len(names),
                       MAPPER_ID[mapper], int(recipe.get("mapper_arg", 0)),
                       int(recipe.get("ngh", 0)), 0, title.ljust(32, b"\0"),
                       0, 0)
    hdr_crc = crc32(hdr0 + table)
    hdr = hdr0[:56] + struct.pack("<I", hdr_crc) + hdr0[60:]
    head = hdr + table
    head += bytes(align(len(head)) - len(head))
    return head + b"".join(blobs)


def parse(blob):
    """Return (header dict, [region dicts]) after validating the container."""
    if len(blob) < HDR_SIZE:
        raise PackError("file too short")
    (magic, ver, hsz, flags, nreg, mapper, marg, ngh, _r16, title, hcrc,
     _r32) = struct.unpack_from(HDR_FMT, blob, 0)
    if magic != MAGIC:
        raise PackError("bad magic")
    if ver != VERSION or hsz != HDR_SIZE:
        raise PackError(f"unsupported version {ver} / header size {hsz}")
    table = blob[HDR_SIZE:HDR_SIZE + ENT_SIZE * nreg]
    if len(table) != ENT_SIZE * nreg:
        raise PackError("truncated region table")
    chk = blob[:56] + bytes(4) + blob[60:HDR_SIZE] + table
    if crc32(chk) != hcrc:
        raise PackError("header CRC mismatch")
    regs = []
    for i in range(nreg):
        t, fl, _r, size, off, crc, _res = struct.unpack_from(
            ENT_FMT, table, ENT_SIZE * i)
        if t not in REGION_NAME:
            raise PackError(f"unknown region type {t}")
        if off % SECTOR:
            raise PackError("region not sector aligned")
        if off + size > len(blob):
            raise PackError("region beyond end of file")
        regs.append(dict(name=REGION_NAME[t], flags=fl, size=size, off=off,
                         crc=crc))
    hdr = dict(version=ver, flags=flags, mapper=mapper, mapper_arg=marg,
               ngh=ngh, title=title.rstrip(b"\0").decode("utf-8", "replace"))
    return hdr, regs


def region_data(blob, reg):
    return blob[reg["off"]:reg["off"] + reg["size"]]


# --------------------------------------------------------------------- CLI
def cmd_pack(a):
    with open(a.recipe) as f:
        recipe = json.load(f)
    base = os.path.join(os.path.dirname(os.path.abspath(a.recipe)),
                        recipe.get("base_dir", "."))
    if a.base_dir:
        base = a.base_dir
    blob = pack(recipe, base, a.no_check)
    with open(a.output, "wb") as f:
        f.write(blob)
    print(f"wrote {a.output}: {len(blob)} bytes")
    cmd_info_blob(blob)


def cmd_info_blob(blob):
    hdr, regs = parse(blob)
    print(f"title : {hdr['title']}")
    print(f"NGH   : {hdr['ngh']:03d}   mapper: "
          f"{MAPPER_NAME.get(hdr['mapper'], hdr['mapper'])}   "
          f"mapper_arg: {hdr['mapper_arg']}")
    total = 0
    for r in regs:
        total += r["size"]
        print(f"  {r['name']:<2} size {r['size']:>10} ({r['size']/1048576:7.3f} MiB)"
              f"  off 0x{r['off']:08X}  crc32 {r['crc']:08X}")
    print(f"  total ROM data {total} bytes ({total/1048576:.3f} MiB)")


def cmd_info(a):
    with open(a.file, "rb") as f:
        cmd_info_blob(f.read())


def cmd_verify(a):
    with open(a.file, "rb") as f:
        blob = f.read()
    hdr, regs = parse(blob)
    ok = True
    for r in regs:
        good = crc32(region_data(blob, r)) == r["crc"]
        ok &= good
        print(f"{r['name']:<2} {'OK' if good else 'CRC MISMATCH'}")
    return 0 if ok else 1


def cmd_unpack(a):
    with open(a.file, "rb") as f:
        blob = f.read()
    _, regs = parse(blob)
    os.makedirs(a.output, exist_ok=True)
    for r in regs:
        path = os.path.join(a.output, r["name"] + ".bin")
        with open(path, "wb") as f:
            f.write(region_data(blob, r))
        print("wrote", path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("recipe")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--base-dir", help="override directory holding the ROM files")
    p.add_argument("--no-check", action="store_true",
                   help="skip the NEO-GEO signature check on the P region")
    p.set_defaults(fn=cmd_pack)
    p = sub.add_parser("info")
    p.add_argument("file")
    p.set_defaults(fn=cmd_info)
    p = sub.add_parser("verify")
    p.add_argument("file")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("unpack")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=cmd_unpack)
    a = ap.parse_args(argv)
    try:
        return a.fn(a) or 0
    except PackError as e:
        print("error:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
