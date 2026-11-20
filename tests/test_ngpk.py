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


if __name__ == "__main__":
    unittest.main(verbosity=2)
