#!/usr/bin/env python3
"""Round-trip and corruption tests for tools/ngpk.py.

Synthetic tests always run.  The real-romset test runs only when
NGPK_ROMDIR points to a directory holding the files named in the recipe.

    python3 -I tests/test_ngpk.py
    NGPK_ROMDIR=/path/to/samsho3 python3 -I tests/test_ngpk.py
"""
import json
import os
import random
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import ngpk  # noqa: E402


def fake_p(size):
    """A P region in 68k byte order carrying the NEO-GEO signature."""
    b = bytearray(random.Random(1).randbytes(size))
    b[0x100:0x107] = b"NEO-GEO"
    return bytes(b)


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(HERE, "_tmp")
        os.makedirs(self.dir, exist_ok=True)
        rnd = random.Random(2)
        p68k = fake_p(0x180000)
        self.p_file = ngpk.swap16(p68k)  # what a MAME-style dump looks like
        self.c_even = rnd.randbytes(0x4000)
        self.c_odd = rnd.randbytes(0x4000)
        self.files = {"p.bin": self.p_file, "c1.bin": self.c_even,
                      "c2.bin": self.c_odd, "s.bin": rnd.randbytes(0x20000),
                      "m.bin": rnd.randbytes(0x20000),
                      "v.bin": rnd.randbytes(0x40000)}
        for n, d in self.files.items():
            with open(os.path.join(self.dir, n), "wb") as f:
                f.write(d)
        self.p68k = p68k
        self.recipe = {"title": "synthetic", "ngh": 0, "mapper": "plain",
                       "regions": {
                           "P": [{"op": "swap16", "files": ["p.bin"]}],
                           "C": [{"op": "interleave8",
                                  "files": ["c1.bin", "c2.bin"]}],
                           "S": [{"files": ["s.bin"]}],
                           "M": [{"files": ["m.bin"]}],
                           "V": [{"files": ["v.bin"]}]}}

    def test_roundtrip(self):
        blob = ngpk.pack(self.recipe, self.dir)
        hdr, regs = ngpk.parse(blob)
        by = {r["name"]: ngpk.region_data(blob, r) for r in regs}
        self.assertEqual(by["P"], self.p68k)
        self.assertEqual(by["P"][0x100:0x107], b"NEO-GEO")
        # de-interleave C and compare with the original chip dumps
        self.assertEqual(by["C"][0::2], self.c_even)
        self.assertEqual(by["C"][1::2], self.c_odd)
        self.assertEqual(by["S"], self.files["s.bin"])
        self.assertEqual(by["M"], self.files["m.bin"])
        self.assertEqual(by["V"], self.files["v.bin"])
        for r in regs:
            self.assertEqual(r["off"] % ngpk.SECTOR, 0)
            self.assertEqual(ngpk.crc32(by[r["name"]]), r["crc"])

    def test_wrong_swap_is_rejected(self):
        self.recipe["regions"]["P"] = [{"op": "concat", "files": ["p.bin"]}]
        with self.assertRaises(ngpk.PackError):
            ngpk.pack(self.recipe, self.dir)

    def test_unequal_interleave_rejected(self):
        with open(os.path.join(self.dir, "c2.bin"), "wb") as f:
            f.write(self.c_odd[:-2])
        with self.assertRaises(ngpk.PackError):
            ngpk.pack(self.recipe, self.dir)

    def test_header_corruption(self):
        blob = bytearray(ngpk.pack(self.recipe, self.dir))
        blob[20] ^= 1  # mapper field
        with self.assertRaises(ngpk.PackError):
            ngpk.parse(bytes(blob))

    def test_unsupported_mapper(self):
        self.recipe["mapper"] = "sma"
        with self.assertRaises(ngpk.PackError):
            ngpk.pack(self.recipe, self.dir)


ROMDIR = os.environ.get("NGPK_ROMDIR")


@unittest.skipUnless(ROMDIR, "set NGPK_ROMDIR to run the real romset test")
class RealRomset(unittest.TestCase):
    def check(self, recipe_name, p_files):
        rpath = os.path.join(HERE, "..", "recipes", recipe_name)
        with open(rpath) as f:
            recipe = json.load(f)
        blob = ngpk.pack(recipe, ROMDIR)
        hdr, regs = ngpk.parse(blob)
        by = {r["name"]: ngpk.region_data(blob, r) for r in regs}

        def rd(n):
            with open(os.path.join(ROMDIR, n), "rb") as f:
                return f.read()

        # P: undo the swap and compare with the concatenated dumps
        self.assertEqual(ngpk.swap16(by["P"]),
                         b"".join(rd(n) for n in p_files))
        self.assertEqual(by["P"][0x100:0x107], b"NEO-GEO")
        # C: split back into the eight original files
        pos = 0
        for i in (1, 3, 5, 7):
            odd, even = rd(f"087-c{i}.c{i}"), rd(f"087-c{i+1}.c{i+1}")
            chunk = by["C"][pos:pos + 2 * len(odd)]
            self.assertEqual(chunk[0::2], odd)
            self.assertEqual(chunk[1::2], even)
            pos += 2 * len(odd)
        self.assertEqual(pos, len(by["C"]))
        self.assertEqual(by["S"], rd("087-s1.s1"))
        self.assertEqual(by["M"], rd("087-m1.m1"))
        self.assertEqual(by["V"], rd("087-v1.v1") + rd("087-v2.v2"))
        # 68k reset vectors sit in the first MiB: SP in RAM, PC in cart/BIOS
        sp = int.from_bytes(by["P"][0:4], "big")
        pc = int.from_bytes(by["P"][4:8], "big")
        self.assertTrue(0x100000 <= sp <= 0x10F300, hex(sp))
        self.assertTrue(pc < 0x1000000, hex(pc))

    def test_samsho3(self):
        self.check("samsho3.json", ["087-epr.ep1", "087-epr.ep2",
                                    "087-epr.ep3", "087-epr.ep4",
                                    "087-p5.p5"])

    def test_samsho3_fswords(self):
        self.check("samsho3_fswords.json", ["fswords/187-p1k.p1",
                                            "fswords/087-p2.sp2"])


# ---- golden models -------------------------------------------------------
# Reference decode of a canonical (MAME order) tile, written after Geolith's
# geo_lspc_tpix (BSD-3): screen pixel p (0..15, no flip) of row y.
def tpix_canonical(c, tile, p, y):
    base = tile * 128 + (((p & 8) ^ 8) << 3) + (y << 2)
    x = p & 7
    v0, v1, v2, v3 = c[base + 0] >> x, c[base + 2] >> x, \
        c[base + 1] >> x, c[base + 3] >> x
    return (v0 & 1) | (v1 & 1) << 1 | (v2 & 1) << 2 | (v3 & 1) << 3


# What the FPGA does with the sdram1 layout: one 8-byte read per row, the
# first 4 bytes feed pixels 0-7 (CA4 = 0), the next 4 feed pixels 8-15; byte
# lane k carries bitplane k.
def tpix_sdram1(c, tile, p, y):
    base = tile * 128 + y * 8 + (4 if p & 8 else 0)
    x = p & 7
    return sum(((c[base + k] >> x) & 1) << k for k in range(4))


def fix_canonical(s, tile, x, row):
    # Geolith fixline: for p in 0..3 byte f = 0x10,0x18,0x00,0x08; low nibble
    # is the left pixel of the pair
    f = (0x10, 0x18, 0x00, 0x08)[x >> 1]
    b = s[tile * 32 + f + row]
    return (b >> 4) & 0xF if x & 1 else b & 0xF


def fix_sdram1(s, tile, x, row):
    b = s[tile * 32 + row * 4 + (x >> 1)]
    return (b >> 4) & 0xF if x & 1 else b & 0xF


class TestLayout(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(3)
        self.c = rnd.randbytes(128 * 64)
        self.s = rnd.randbytes(32 * 64)

    def test_roundtrip(self):
        self.assertEqual(ngpk.c_from_sdram1(ngpk.c_to_sdram1(self.c)), self.c)
        self.assertEqual(ngpk.s_from_sdram1(ngpk.s_to_sdram1(self.s)), self.s)

    def test_is_permutation(self):
        self.assertEqual(sorted(ngpk.c_to_sdram1(self.c)), sorted(self.c))
        self.assertNotEqual(ngpk.c_to_sdram1(self.c), self.c)

    def test_sprite_pixels_match_golden(self):
        out = ngpk.c_to_sdram1(self.c)
        for tile in range(64):
            for y in range(16):
                for p in range(16):
                    self.assertEqual(tpix_sdram1(out, tile, p, y),
                                     tpix_canonical(self.c, tile, p, y))

    def test_fix_pixels_match_golden(self):
        out = ngpk.s_to_sdram1(self.s)
        for tile in range(64):
            for row in range(8):
                for x in range(8):
                    self.assertEqual(fix_sdram1(out, tile, x, row),
                                     fix_canonical(self.s, tile, x, row))

    def test_bad_sizes(self):
        with self.assertRaises(ngpk.PackError):
            ngpk.c_to_sdram1(bytes(100))
        with self.assertRaises(ngpk.PackError):
            ngpk.s_to_sdram1(bytes(31))

    def test_pack_flags_and_unpack(self):
        d = tempfile.mkdtemp()
        for n, b in (("p", fake_p(1 << 20)), ("c1", self.c[:4096]),
                     ("c2", self.c[4096:8192]), ("s", self.s)):
            with open(os.path.join(d, n), "wb") as f:
                f.write(b)
        rec = {"title": "t", "regions": {
            "P": [{"files": ["p"]}],
            "C": [{"op": "interleave8", "files": ["c1", "c2"]}],
            "S": [{"files": ["s"]}]}}
        for layout, fl in (("canonical", 0), ("sdram1", 1)):
            blob = ngpk.pack(rec, d, layout=layout)
            hdr, regs = ngpk.parse(blob)
            by = {r["name"]: r for r in regs}
            self.assertEqual(by["C"]["flags"], fl)
            self.assertEqual(by["S"]["flags"], fl)
            self.assertEqual(by["P"]["flags"], 0)
            canon = ngpk.to_canonical("C", by["C"]["flags"],
                                      ngpk.region_data(blob, by["C"]))
            exp = bytearray(8192)
            exp[0::2], exp[1::2] = self.c[:4096], self.c[4096:8192]
            self.assertEqual(canon, bytes(exp))
        with self.assertRaises(ngpk.PackError):
            ngpk.pack(rec, d, layout="nope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
