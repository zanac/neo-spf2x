# Architecture of the Neo Geo AES cartridge with microSD

Project status: **format, packer and loader are written and tested; the PCB does
not exist yet, and the FPGA gateware is simulated but not proven on a console.**
(The MVS variant is described in `docs/MVS.md`.) This document separates what has
been verified from what is still a proposal or an open point.

## 1. How it works

```
PC                    microSD                 Cartridge
recipe + ROMs  --ngpk.py-->  game.ngpk  --->  MCU (FatFS + loader)
                                                  |  writes into SDRAM
                                                  v
                                   FPGA <--> 64 MiB SDRAM
                                     |
                                     +-- AES cartridge logic towards the console
```

1. On the PC `tools/ngpk.py` converts a game's romset into an `.ngpk` file.
2. At power-on the MCU reads the `.ngpk` from the microSD, checks the CRCs and
   copies the regions into SDRAM (`firmware/ngsd_loader.c`).
3. The MCU writes the region sizes and addresses into the FPGA registers, then sets
   `CTRL.RUN`.
4. The FPGA serves the data from the SDRAM to the console, replicating what the ROMs
   and chips of a real cartridge would do.

Modularity lives in two places: the `.ngpk` format (game details stay in the
packer) and the `mapper` field (logic differences stay in the gateware, selected by
a register).

## 2. Facts verified on the neogeodev wiki

* The AES connector has 200 contacts (2 × 2 × 50).
* AES cartridges contain a **NEO-ZMC2** chip (or PRO-CT0); MVS ones do not.
  NEO-ZMC2 merges NEO-ZMC (Z80 bank switching, inputs `SDA0, SDA1, SDA8-SDA15`,
  outputs `MA11-MA21` towards the M ROM) and PRO-CT0 (sprite serializer).
* PRO-CT0 takes the C data in parallel (`C0-C31`, "2×16 bit", everything needed for
  a line of 8 pixels), latches it on the falling edge of `12M` when `LOAD` is
  present, emits one pixel per falling edge of `12M`, reverses the order with `H`
  (horizontal flip) and produces `DOTA/DOTB` and `GAD0-3/GBD0-3`.
* Tile: 16×16 px at 4 bpp = 128 bytes. Odd C ROMs hold bitplanes 0-1, even ones
  bitplanes 2-3.
* Required speeds: C ROM under 250 ns (7 mclk); P ROM at least 150 ns (with
  configurable wait states); ADPCM-A V ROM anything (> 2 µs), ADPCM-B 250 ns.
* P bank switching: a write (word, or byte at an odd address) in the
  `$200000-$2FFFFF` window drives `/PORTWEL` low and latches D0/D1 on A20/A21 of P2;
  the latches clear at reset; the window is 1 MiB.

**Important consequence:** on AES the cartridge carries more than memory. The FPGA
must **replicate NEO-ZMC2** (Z80 bank switching and pixel serializer) in addition to
the P latch. The serializer has real timing constraints: the C data must arrive from
the SDRAM within 250 ns, so prefetch and careful bank/row access handling are needed.

**AES pinout (from `docs/AES_PINOUT.md`) and the FPGA's real role.** The CHA
connector does not carry the C ROM data: it takes as input the tile address
(`P0-P23`) with the timing signals (`CA4`, `PCK1B`, `PCK2B`, `2H1`, `12M`, `LOAD`,
`EVEN`, `H`, `8M`, `24M`) and expects as output the already serialized pixels
(`DOTA`, `DOTB`, `GAD0-3`, `GBD0-3`) and the fix layer data (`FIXD0-7`). So the
FPGA: reads `P0-P23`, fetches the data from the SDRAM, serializes it with the
NEO-ZMC2 rules (including `H` for the flip and `LOAD`) and drives the outputs; in
addition it must serve the Z80 bus (`SDA0-15`, `SDD0-7`, `SDMRD`, `SDROM`) with the
M ROM bank switching, the ADPCM buses (`SDPAD/SDRAD`...) for the V ROM and, on the
PROG side, the 68k bus (`D0-D15`, `A1-A19`) with the bank latch. All these signals
are at console level (5 V), so translators or 5 V-tolerant parts are needed.

## 3. SDRAM map (`ngsd-64M` profile)

A design choice, changeable together with the gateware.

| Region | Base        | Maximum |
|--------|-------------|---------|
| P      | `0x0000000` | 8 MiB   |
| V      | `0x0800000` | 16 MiB  |
| S      | `0x1800000` | 1 MiB   |
| M      | `0x1900000` | 1 MiB   |
| C      | `0x1A00000` | 38 MiB  |

Total 64 MiB. Samurai Shodown III (the supplied example) takes 35.25 MiB: P 3,
C 26, V 6, S 0.125, M 0.125. The `spf2ng` game takes 45.4 MiB (P 5, C 32, V 8,
S 0.125, M 0.25) and fits, with 6 MiB left free on C. Games with C above 38 MiB or
with a separate ADPCM-B are rejected by the loader with an explicit error
(`NGPK_E_PROFILE`). The CHA board has a second SDRAM footprint (128 MiB) for the
`ngsd-128M` profile (`firmware/ngsd_loader.c`): P 16 at `0`, V 16 at `0x1000000`, VB 4 at
`0x2000000`, S 1 at `0x2400000`, M 1 at `0x2500000`, C 64 at `0x2600000` (MiB). It covers every
set in MAME's list (largest 90 MiB, `docs/PROTECTIONS.md`); the gateware side is
`ng_sdram.v` with `addr[26]` selecting the chip.

## 4. Firmware ↔ FPGA contract

32-bit registers (`firmware/ngsd_loader.h`):

| Register | Address | Meaning |
|----------|---------|---------|
| `CTRL` | `0x00` | bit0 `RUN`: 0 = cartridge stopped, 1 = game running; bit1 `STUB`: serve the boot stub from the boot RAM (cleared by the FPGA when the 68k asks) |
| `MAPPER` | `0x01` | mapper id of the package |
| `MAPPER_ARG` | `0x02` | mapper argument |
| `SIZE_x` | `0x10 + (type-1)` | bytes present in the region (0 if absent) |
| `BOOT_ADDR` | `0x30` | index (16-bit word) of the boot RAM for the next write |
| `BOOT_DATA` | `0x31` | 16-bit word, written at the index, which then advances |
| `ADDR_x` | `0x20 + (type-1)` | SDRAM base of the region |

The loader sets `CTRL = STUB` and loads the boot RAM before writing into SDRAM, and
sets `RUN` (and the stub's "ready" flag) only after all CRCs are correct. The
physical transport (1-bit SPI or QSPI between MCU and FPGA) is not chosen yet: the
loader only sees it as `sdram_write` and `fpga_reg`.

Estimated load times (not measured): for 35 MiB about 6 s with 50 MHz SPI, 2-3 s
with 4-bit SDIO.

## 5. What has been tested

* Packer: byte-by-byte round trip on the example romset (two program versions),
  rejection of a wrong swap, interleave of different lengths, unknown mapper,
  corrupted header.
* C loader (compiled with AddressSanitizer and UBSan): loads the whole 35 MiB package
  into a simulated SDRAM and compares every region with the extracted files; tries
  buffers of 512, 1000, 4096 and 65536 bytes; checks that a flipped bit in the data
  blocks `RUN`, and that a corrupted header or a game that is too large do not touch
  the hardware.
* C and S `sdram1` layout: round trip, permutation, pixel-by-pixel comparison with a
  reference model of the canonical decoding, region flags, and rejection of a
  canonical package by the loader (`NGPK_E_LAYOUT`).
* Gateware (Icarus Verilog): sprite fetch and serializer, fix, P bank latch, Z80
  banking, boot stub, whole system with an SDRAM chip model, MVS variant. See
  `docs/GATEWARE.md`.
* How to run them: `tests/run_all.sh [romset_folder]`.

## 6. Open points (to resolve before the PCB)

0. **What the gateware must do is now largely clear** (sprites, fix, P bank
   switching, NEO-ZMC): see `docs/TIMING.md`, derived from the Geolith source and the
   NeoGeo_MiSTer core. The nanosecond delays on the connector are not, and are listed
   in section 7 of that document.
1. **AES pinout: names and pin numbers known, the rest not.** The signal names and
   pin numbers of PROG and CHA come from the `neogeo-diag-aes-prog` repo (see
   `docs/AES_PINOUT.md`). Directions, levels and the **margins in nanoseconds** of
   `PCK1B/PCK2B`, `LOAD`, `CA4`, `EVEN`, `H`, `2H1`, `12M` and of the ADPCM bus are
   missing. The order of events is known from the MiSTer core; the margins must be
   measured with a logic analyzer on a console.
2. **Boot: solution chosen and simulated, not proven on a console** (see
   `docs/BOOT.md`). The `ROMWAIT`/`PWAIT`/`PDTACK` pins only add fixed wait states,
   so they do not hold the console still: instead the FPGA serves the 68k a boot stub
   (the game's header + 60 bytes of code) until the MCU is done, then the console is
   restarted onto the game.
3. **C and S data layout in SDRAM: defined, not verified on hardware.** The packer
   produces the `sdram1` layout (see `docs/FORMAT.md`), a per-tile-row permutation,
   and the loader rejects packages with another layout (`NGPK_E_LAYOUT`). The
   permutation is consistent with a model of Geolith's decoding (automatic tests), but
   the `CA4` ↔ tile half and byte-lane ↔ bitplane correspondence stays a hypothesis
   until the gateware runs on a console.
4. **P1/P2 split.** For Samurai Shodown III I deduced from a file comparison that
   `ep1+ep2` is P1 (1 MiB) and `ep3+ep4+p5` is P2 (2 MiB, equal to `sp2` of the fswords
   version). It must be confirmed with the board's data.
5. **Mapper.** Anything requiring protections (SMA, PCM2, CMC, PVC...) is not
   supported. That Samurai Shodown III is `plain` I consider likely but have not
   verified.
6. **Component choice: proposal in `docs/COMPONENTS.md`.** With 162 console-side
   signals (AES) about 220 I/Os are needed: proposed FPGA ECP5 LFE5U-45F in caBGA554
   (245 I/O), 64 MiB SDRAM at ≥ 133 MHz, RP2040, about 11 16-bit translators. The
   mechanics, signal directions and 5 V current remain open. The MVS (182 signals)
   also fits the 45F with little margin; the 85F in the same package is the fallback.
7. **Game selection.** For now a configuration file on the SD plus a button to move
   to the next one. A menu run by the Neo Geo itself is possible but is another phase.
8. **License.** GPL-3.0-or-later (`LICENSE` file). The reference core (NeoGeo_MiSTer)
   has a v2 `LICENSE` and files with "v2 or later" and "v3 or later" headers:
   GPL-3.0-or-later is compatible with both, but not with any "v2 only" files that I
   have not checked one by one.

## 7. Next steps

1. Derive the signal timings (point 1) and settle the boot strategy (point 2). The
   AES contact footprints (public domain) are already available in the
   `neogeo-diag-kicad-library` repo's library.
2. Choose FPGA/MCU/SDRAM and write the KiCad schematic (AES and MVS, `docs/PCB.md`).
3. Gateware: ADPCM bus, then real-console validation.
4. Write the MCU's hardware layer (SD, SPI/QSPI towards the FPGA) under the existing
   loader.
5. Prototype.
