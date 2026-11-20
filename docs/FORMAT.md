# NGPK v1 format (Neo Geo Pack)

An `.ngpk` file holds **all the ROMs of a game** in a canonical byte order,
independent of the game and of the hardware. All game-specific work (swap,
interleave, concatenation) is done by the packer on the PC; the cartridge firmware
just copies the regions into SDRAM. Adding a game means writing a JSON *recipe*,
not touching firmware or gateware.

All integer fields are **little-endian**. Region data is aligned to 512 bytes (one
SD sector) and padded with zeros up to the next sector.

## Header (64 bytes, offset 0)

| Off | Size | Field        | Notes |
|----:|-----:|--------------|-------|
| 0   | 4    | magic        | `"NGPK"` |
| 4   | 2    | version      | 1 |
| 6   | 2    | hdr_size     | 64 |
| 8   | 4    | flags        | 0, reserved |
| 12  | 4    | nregions     | 1..8 |
| 16  | 2    | mapper       | 0 = `plain` (see below) |
| 18  | 2    | mapper_arg   | 0 for `plain`; 1 reserved for a single 2 MiB P |
| 20  | 2    | ngh          | NGH number, 0 for homebrew |
| 22  | 2    | reserved     | 0 |
| 24  | 32   | title        | UTF-8, zero-padded (max 31 bytes) |
| 56  | 4    | hdr_crc      | CRC-32 of header (with this field at 0) + region table |
| 60  | 4    | reserved     | 0 |

## Region table (nregions × 32 bytes, offset 64)

| Off | Size | Field    | Notes |
|----:|-----:|----------|-------|
| 0   | 1    | type     | 1=P 2=C 3=S 4=M 5=V 6=VB |
| 1   | 1    | flags    | bits 0-3: data layout (see "Region layouts"); bits 4-7 reserved, 0 |
| 2   | 2    | reserved | 0 |
| 4   | 4    | size     | bytes of real data (without padding) |
| 8   | 4    | file_off | offset in the file, multiple of 512 |
| 12  | 4    | crc32    | CRC-32 (zlib) of the `size` bytes |
| 16  | 16   | reserved | 0 |

Validity rules (the C parser checks all of them; the packer respects them by
construction): one region per type; `size > 0`; `file_off` a multiple of 512 and not
before the end of the table (rounded up to 512); non-overlapping regions; correct
header CRC. The packer writes the regions in the order P, S, M, V, VB, C.

## Canonical region contents

| Region | Content in the package |
|--------|------------------------|
| **P**  | 68k program in **68k byte order** (big-endian). MAME-style dumps are word-swapped, so the recipe uses `swap16`. The packer checks that `"NEO-GEO"` is at 0x100: if missing, the swap is almost always wrong. The first 1 MiB is P1 (68k `$000000`); the rest is P2, in 1 MiB banks visible in the `$200000-$2FFFFF` window. |
| **C**  | Sprite tiles. For each chip pair `(c_odd, c_even)` the bytes are interleaved: `out[0::2] = c1`, `out[1::2] = c2`; the pairs are then concatenated in order (c1/c2, c3/c4, ...). This is the layout MAME uses. A 16×16 4 bpp tile takes 128 bytes, so `size` is a multiple of 128. |
| **S**  | Fix layer tiles, raw dump. |
| **M**  | Z80 code (M1), raw dump. |
| **V**  | ADPCM samples, files concatenated in order (v1, v2, ...). Used by both ADPCM-A and ADPCM-B. |
| **VB** | Only for games with a separate ADPCM-B ROM (older titles). The format provides for it; the 64M profile has no slot for it and rejects such games. |

## Region layouts (flags, bits 0-3)

Only C and S have an alternative layout; for the other regions the value is 0.

* `0 = canonical`: MAME order, as described above.
* `1 = sdram1`: reordering done by the packer so that the FPGA reads a tile row with
  a single sequential burst. It is the layout required by the `ngsd-64M` profile:
  the loader rejects a package with a different layout with `NGPK_E_LAYOUT`,
  without touching the hardware. The `pack` command uses `sdram1` by default
  (`--layout canonical` for the other); `unpack --canonical` restores the MAME order.

**C, `sdram1`.** For tile `t` and row `y` (0..15) there are 8 bytes at
`t*128 + y*8`: first the 4 bytes of the half at canonical offset `+0x40` (pixels 0-7
on screen, without flip, selected with `CA4 = 0`), then the 4 bytes of the half at
`+0x00` (pixels 8-15). Each group of 4 canonical bytes `[b0 b1 b2 b3]` is reordered
to `[b0 b2 b1 b3]`, so that byte `k` carries bitplane `k`.

**S, `sdram1`.** For tile `t` and row `r` (0..7) there are 4 bytes at
`t*32 + r*4`, taken from the canonical order at offsets `+0x10+r, +0x18+r,
+0x00+r, +0x08+r`: each byte holds two adjacent pixels (low nibble on the left).

`tests/test_ngpk.py` (`TestLayout`) compares every pixel decoded from the `sdram1`
layout with a model of the canonical decoding written following `geo_lspc_tpix` and
the fix layer routine of Geolith.

**Hypothesis not verified on hardware.** The correspondence `CA4 = 0` ↔ `+0x40` half
and the byte-lane ↔ bitplane assignment are inferred from the Geolith and
NeoGeo_MiSTer sources, not measured on a cartridge. If the gateware showed the
halves swapped, changing one constant in the packer is enough.

The format describes the **data**; how the C bytes are distributed on the
`CR0-CR31` lines and how they are used by the serializer is the gateware's job.

## Mapper

The `mapper` field says which cartridge logic the game needs.

* `0 = plain`: only the P bank-switching latch (write in the `$200000-$2FFFFF`
  window, bits D0/D1 towards A20/A21 of P2, cleared at reset) and the basic AES
  cartridge logic. It is the only mapper supported today.
* Values reserved for the future: protections and encryptions (SMA, PCM2, CMC,
  PVC...; the catalogue and the proposed order are in `docs/PROTECTIONS.md`). Packer and loader reject unknown mappers instead of loading a game that
  would not work.

## JSON recipe (packer input)

```json
{
  "title": "Game name",
  "ngh": 87,
  "mapper": "plain",
  "base_dir": ".",
  "regions": {
    "P": [{"op": "swap16", "files": ["a.p1", "b.p2"]}],
    "C": [{"op": "interleave8", "files": ["c1.bin", "c2.bin"]},
          {"op": "interleave8", "files": ["c3.bin", "c4.bin"]}],
    "S": [{"files": ["s1.bin"]}],
    "M": [{"files": ["m1.bin"]}],
    "V": [{"files": ["v1.bin", "v2.bin"]}]
  }
}
```

Operations per segment (the segments of a region are concatenated):

* `concat` (default): files concatenated as they are.
* `swap16`: every file is byte-swapped in pairs, then concatenated.
* `interleave8`: exactly two files `[even, odd]` of the same length, bytes
  interleaved.

Included recipes: `recipes/samsho3.json` and `recipes/samsho3_fswords.json` (same
game, two program versions: they show that changing game or revision only means
changing the recipe) and `recipes/spf2ng.json`, the project's game.
