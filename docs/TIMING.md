# Behaviour and timing derived from Geolith

**Sources.** Geolith source (libretro port, three-clause BSD license), read but not
run: `src/geo_lspc.c`, `geo_m68k.c`, `geo_z80.c`, `geo_neo.c`. Plus the *PRO-CT0*
page of the neogeodev wiki. The original source is on GitLab, not reachable from
here; the libretro port contains a copy.

**Important limit.** Geolith is an emulator: it reproduces *what* is read and
*when*, at the level of 68k cycles and scanlines. It does **not** reproduce the
signal edges on the connector (`PCK1B`, `LOAD`, `CA4`...). The wiki, on the PRO-CT0
page, has no waveforms or cycle counts. So below there is everything needed to decide
*what* the gateware must do, not yet *with which delays*. The list of what is missing
is at the bottom.

Each point is marked: **[Geolith]** the emulator code says so, **[wiki]** the
documentation, **[calc]** I derived it.

## 1. Video frame

* **[Geolith]** 384 pixels per line × 264 lines; 768 68k cycles per line.
* **[calc]** With the 68k at 12 MHz a line lasts 64 µs (15.625 kHz), the pixel clock is
  6 MHz (24M/4), a pixel lasts 166.7 ns and a frame 16.9 ms (about 59.2 Hz). It
  matches the known Neo Geo values.

## 2. Sprites (C ROM)

All the sprite logic is **in the console** (LSPC): chaining, shrinking through the L0
ROM, the 96-sprites-per-line limit, auto-animation, vertical flip. The cartridge only
sees the final address and the `H` signal.

* **[Geolith]** The tile number is 20 bits (low 16 bits plus 4 high from the VRAM), the
  tile takes 128 bytes: byte address = `tile × 128`.
* **[MiSTer, section 8]** `P0-P23` are 20 bits of tile plus 4 of row (0-15): each
  address identifies a row of 16 pixels. Geolith alone does not say so.
* **[Geolith]** A 16×16 tile is read in two halves of 8 pixels, one per value of `CA4`
  (the wiki says `CA4` selects the block columns). Without horizontal flip: pixels 0-7
  from the half at `tile + 0x40`, pixels 8-15 from the half at `tile + 0x00`; with flip
  the halves swap and the pixel order is reversed. Inside a half, row `y` is at
  `+ 4·y` (4 bytes = 32 bits for 8 pixels, consistent with the wiki's `C0-C31`).
* **[Geolith]** In the interleaved layout that our `.ngpk` also uses, the 4 bytes of a
  row `b0 b1 b2 b3` give the bitplanes like this: plane 0 = `b0`, plane 1 = `b2`,
  plane 2 = `b1`, plane 3 = `b3`. That is, planes 0-1 come from the odd chip (c1),
  planes 2-3 from the even chip (c2): it matches the wiki.
* **[Geolith]** Pixel `x` of a half uses bit `x` of each byte (the leftmost pixel is
  bit 0). With `H` active the order is reversed (`x ^ 7`). Vertical flip: the row
  becomes `15 - y`. Value 0 is transparent.
* **[Geolith]** The tile number is masked to the size of the C ROM (`% csz`): on a real
  cartridge the high addresses "fold back" onto the memory present. Our FPGA must do
  the same (tile modulo C size).
* **[calc]** In the worst case a line requires 96 tiles × 2 32-bit reads = 192 C reads;
  over 64 µs that is about 333 ns on average per read (two pixel clocks). It is a
  budget hypothesis, not a documented figure.

## 3. Fix layer (S ROM)

* **[Geolith]** 8×8 tiles of 32 bytes; a row of 8 pixels is 4 bytes, at positions
  `+0x10, +0x18, +0x00, +0x08` plus the row number. Each byte carries 2 pixels: low
  nibble on the left, high on the right.
* On the connector the S ROM goes through `FIXD0-7` (8 bits): the cartridge answers an
  address carried by the `P` bus, latched on `PCK2B`: the wiring is described in section
  8 (16-bit word plus `S2H1` to choose the byte).
* **[Geolith]** Some cartridges switch the fix bank per line or per tile (types 1 and 2):
  they are not in the `plain` mapper.

## 4. P ROM: bank switching

* **[Geolith]** The 68k sees the first 1 MiB fixed; the `$200000-$2FFFFF` window shows
  bank `n` at offset `1 MiB × (n + 1)` of the P. The written number is masked with
  (next power of two of the number of banks) − 1. It is the same scheme as our `.ngpk`
  (P1 = first 1 MiB, then the banks).
* **Discrepancy to resolve.** Geolith only acts on writes at address `>= $2FFFF0`; the
  wiki describes the latch firing on **any** write (word, or odd byte) in the window. For
  the gateware it is better to follow the hardware described by the wiki, which is a
  superset.
* **[Geolith]** Variants with protection (SMA, PVC, "ct0", linkable) have their own
  rules: they confirm that they go in separate mappers.

## 5. M ROM and NEO-ZMC (Z80)

* **[Geolith]** Z80 map: `0x0000-0x7FFF` fixed (start of M1); `0x8000-0xBFFF` 16 KiB
  bank 0; `0xC000-0xDFFF` 8 KiB bank 1; `0xE000-0xEFFF` 4 KiB bank 2; `0xF000-0xF7FF`
  2 KiB bank 3; `0xF800-0xFFFF` work RAM.
* **[Geolith]** The bank is changed with a Z80 **port read**: port `0x0B` sets bank 0,
  `0x0A` bank 1, `0x09` bank 2, `0x08` bank 3. The bank number is the **high byte of the
  port address** (`A15-A8`), masked with `0x0F`, `0x1F`, `0x3F`, `0x7F`; the offset is
  number × bank size. With these masks each window covers 256 KiB: it is the limit
  Geolith imposes on the M1. The NeoGeo_MiSTer core (section 8) uses one more bit per
  window and reaches 512 KiB: for the gateware the latter is followed, as it models the
  real chip.
* **[wiki]** NEO-ZMC has as inputs `SDA0, SDA1, SDA8-SDA15` and as outputs the high
  addresses of the M ROM: consistent with the above (`SDA0/1` choose the bank, `SDA8-15`
  carry the value).
* **[calc]** The M1 of the `spf2ng` game is 256 KiB: it fits both models.
* Which strobes (`SDRD0`, `SDRD1`...) qualify the port read on the connector remains to
  be confirmed.

## 6. `.neo` format (a hint, not used yet)

Geolith only loads `.NEO` (TerraOnion): 4096-byte header (`'N' 'E' 'O' 1`, sizes of P, S,
M1, V1, V2, C as 32-bit little-endian integers, then year, genre, NGH, name,
manufacturer), data after the header. A `.neo → .ngpk` importer is feasible; I have not
written it because I have no `.neo` file to verify it with.

## 7. What can NOT be derived from here

Updated after reading the NeoGeo_MiSTer core (section 8): the points on the meaning of
`P0-P23`, on the wiring towards the S and C ROMs and on the production of
`DOTA/DOTB/GAD/GBD` were resolved there. Still open:

1. Connector timings **in nanoseconds**: setup and hold of `PCK1B`, `PCK2B`, `LOAD`,
   `CA4`, `EVEN`, `H`, `2H1` with respect to `12M`, `24M`, `8M`. The MiSTer core works at
   48 MHz with clock enables, so it gives the order of events, not the analog margins.
2. The exact `12M` edge that samples `CR` (the core uses an enable called "12M_N", the
   notes speak of a rising edge): polarity to verify.
3. ADPCM bus: `SDPMPX`/`SDRMPX` multiplexing and timing.
4. Semantics of `PDTACK`, `ROMWAIT`, `PWAIT0/1` (for holding the console still).
5. The wiki writes "under 250 ns (7 mclk)" for the C ROM: 7 periods of a 24 MHz clock are
   292 ns, 250 ns are 6. I do not know which of the two is the right figure.

## 8. From the NeoGeo_MiSTer core (furrtek and others)

**Source.** `github.com/MiSTer-devel/NeoGeo_MiSTer`: a complete FPGA implementation of
the Neo Geo, with the chips split into modules (`rtl/video/zmc2_dot.v`, `rtl/io/zmc.v`,
`rtl/video/neo_273.v`, `rtl/video/lspc2_clk.v`) and a notes file by the author
(`DEV_NOTES.md`). **GPL license** (`LICENSE` file v2, some headers v3 or later). I read
it to understand the behaviour and this section is written in my own words; **I did not
copy code**. If our gateware ever reuses code from that core, it would inherit the GPL:
this must be decided beforehand.

**[MiSTer] Clocks.** Master 24 MHz; `12M`, `6M`, `3M`, `1.5M` are divisions by 2, 4, 8,
16; `8M` is 24M/3 and `4M` is 24M/6.

**[MiSTer] Serializer (zmc2_dot).** A 32-bit shift register loaded from `CR` when `LOAD`
is active, on a `12M` tick; then at every tick it shifts by **two pixels** (the four
one-byte lanes advance by 2 bits), in the direction chosen by `H`. The output is two
pixels at a time, `GAD` (pixel A) and `GBD` (pixel B), 4 bits each; `EVEN` and `H` choose
which bits form the pair (parity of X and direction). `DOTA` and `DOTB` are 1 if the pixel
is non-zero, i.e. not transparent.
**[calc]** 8 pixels = 4 ticks of 83.3 ns = 333 ns for every 32-bit `CR` read. It matches
the budget estimate in section 2.

**[MiSTer] Addresses on the P bus.** The `P` bus is multiplexed: the cartridge captures
different values on two edges.
* On `PCK1B` (sprites): `PBUS[15:0]` are the low 16 bits of the tile number,
  `PBUS[19:16]` the tile row (0-15), `PBUS[23:20]` the high 4 bits of the tile. In
  practice `P0-P23` = tile (20 bits) + row (4 bits), and each address identifies 8 bytes,
  i.e. a row of 16 pixels (64 bits); `CA4` chooses the 32-bit half sent to the serializer.
* On `PCK2B` (fix): `PBUS[11:0]` are the tile number and `PBUS[15:12]` four position bits
  in the tile; together they form a 16-bit word address (128 KiB of S ROM), and `S2H1`
  chooses the high or low byte for `FIXD0-7`.

**[MiSTer] Read triggers** (from `DEV_NOTES.md`): the C read starts when `PCK1B` rises, the
S read when `PCK2B` rises, the 68k bus when `nROMOE` or `nPORTOE` fall. The core described
in the file uses 120 MHz SDRAM (5 × 24M, up to 144 MHz) and must insert **one wait state**
on the 68k. For us it means that the SDRAM latency matters and that the PROG wait signals
(`ROMWAIT`, `PWAIT0/1`, `PDTACK`) must be truly understood.

**[MiSTer] Reorganization at load time.** The core does not keep the data in file order: it
reorders it while loading. For the fix it puts pairs of pixels adjacent so that a single
16-bit read serves 4 pixels; for sprites it arranges the bytes so that a row of 16 pixels
(64 bits) is four consecutive 16-bit words, readable in a burst, with `CA4` choosing the
half. This confirms the choice of a loader that prepares the data, but it means **the
canonical `.ngpk` layout is not what the FPGA will read**: a defined permutation is needed
(in the packer, in the loader or in the write towards the SDRAM). The exact detail is in
the loader of the MiSTer software (`support/neogeo/loader.cpp` according to the notes),
which I have not read yet.

**[MiSTer] NEO-ZMC (Z80).** Four window registers, one per size (2, 4, 8, 16 KiB), which
at reset point to the same address area ("identity" windows). On the rising edge of
`SDRD0` the value present on `SDA15-SDA8` is latched, and `SDA1-SDA0` choose the window.
The `MA[18:11]` output is the high address of the M ROM: below `0x8000` the address passes
through as it is. The addresses are therefore up to 19 bits (512 KiB).

**Limits of this source.** The core is a working register-level model, not a measurement
of the connector. The GPL license and the details of `loader.cpp` are the two points to
close before writing the gateware.

## 9. Leads to fill the gaps

* C and S layout: our `sdram1` (see `docs/FORMAT.md`) is a design choice, verified only
  against a model of Geolith's decoding. Main_MiSTer's `loader.cpp` (`support/neogeo/`)
  contains the permutation MiSTer uses and has not been read: comparing it would be an
  independent check of the `CA4` ↔ tile half and lane ↔ bitplane hypotheses.
* The PRO-CT0 page of the wiki points to a PRO-CT0 Verilog source (`Ct0.zip`, by furrtek)
  and to its schematic: useful to compare the serializer with `zmc2_dot`. I could not read
  them from here.
* Measurements with a logic analyzer on a console with a real cartridge, for the margins
  in nanoseconds.

## 10. MVS note

The MVS connector gives the console-side serializer parallel `CR0-CR31` data and the
three clocks `24M`, `12M`, `8M`; see `docs/MVS.md`. Everything in sections 2-5 about *what*
is read applies unchanged; section 8's serializer is not needed on the cartridge.

## 11. ADPCM bus (YM2610)

From the wiki, not measured. The YM2610 reads the V ROM on two multiplexed buses:

* **ADPCM-A**: `SDRAD[7:0]` + `SDRA8/9` carry `A[9:0]` at the rising edge of `SDRMPX` and
  `A[19:10]` at the falling edge; `SDRA[23:20]` are direct. One read every ≈ 1.5 µs.
* **ADPCM-B**: `SDPAD[7:0]` + `SDPA8-11` carry `A[11:0]` at the rising edge and `A[23:12]` at
  the falling edge. One read every ≈ 250 ns.
* With `SDROE`/`SDPOE` low the ROM drives the data; the chip latches on the rising edge.

`ng_adpcm.v` latches the two halves, requests the byte from SDRAM and answers inside the
window; if the data is late it counts it in `late` instead of stalling. The nanosecond
margins are **unverified** (SDRAM latency against the ≈ 250 ns of port B is the tight one).
