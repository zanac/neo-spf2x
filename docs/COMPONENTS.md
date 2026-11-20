# Component choice (proposal, to be confirmed)

**Correction to an earlier proposal of mine.** I had suggested a Cyclone 10 LP with 64 MiB
SDRAM. Counting the real connector signals (`hardware/gen_signals.py` from
`docs/AES_PINOUT.md`) that choice does not hold: the **console-side signals are 162**, and
the number of useful FPGA I/Os rises to about 220.

## 1. I/O budget

| Item | FPGA pins |
|------|----------:|
| Console signals (PROG 82 + CHA 80, power and audio excluded) | 162 |
| 16-bit SDRAM (16 DQ, 13 A, 2 BA, CKE, CS, RAS, CAS, WE, 2 DQM, clock) | 39 |
| MCU link (8-bit bus + strobes, or SPI/QSPI) | ~12 |
| Translator direction, LED, button, misc | ~8 |
| **Total** | **~221** |

Of the 162 signals, by name: 99 inputs (addresses, strobes, clocks, bank bits), 22 outputs
(pixel, fix, wait lines), 40 bidirectional (`D0-D15`, `SDD0-7`, multiplexed ADPCM buses
`SDPAD`/`SDRAD`), 1 uncertain (`4MB`). **Directions are deduced from the names**, not
verified (`basis` column of `hardware/signals.csv`).

### MVS budget

The MVS has **182 signals** (`docs/MVS.md`): 182 + 39 + ~12 + ~8 ≈ **241** with the
parallel MCU bus, ≈ 233 with an SPI link. On the 45F caBGA554 (245 I/O) very few pins are
left: for the MVS the **LFE5U-85F in the same caBGA554** (259 I/O) is planned.

## 2. FPGA

Data from the manufacturers' sites (consulted today):

| Family / device | Package | User I/O | Enough (≥ ~230 with margin)? |
|-----------------|---------|---------:|------------------------------|
| Cyclone 10 LP 10CL016/025 | UBGA-256 | 162 / 150 | no |
| Cyclone 10 LP 10CL010 | UBGA-256 | 176 | no |
| ECP5 LFE5U-25F / 45F | caBGA256 | 197 | no |
| ECP5 LFE5U-45F | caBGA381 | 203 | no |
| **ECP5 LFE5U-45F** | **caBGA554 (23×23 mm)** | **245** | **yes** |
| ECP5 LFE5U-85F | caBGA554 | 259 | yes (larger than needed) |
| Cyclone 10 LP 10CL025/040 | UBGA-484 | 325 | yes |

**Proposal: Lattice ECP5 LFE5U-45F in caBGA554.** It supports 3.3 V LVCMOS I/O, is enough
as logic (44 k LUT against the few thousand of the current gateware) and has an open
toolchain (Yosys + nextpnr-ecp5 + openFPGALoader), in line with the rest of the project:
**whether nextpnr-ecp5 supports this exact package is to be verified** before ordering. The
alternative is a Cyclone 10 LP 10CL025 in UBGA-484 with Quartus Lite. In both cases a BGA is
needed, hence a multi-layer PCB and factory assembly.

The existing gateware is generic Verilog: it does not change with the family (PLL,
constraints and SDRAM I/O change).

## 3. Memory and MCU

* **SDRAM:** 512 Mbit (64 MiB) × 16, SDR, 143-166 MHz class (grade -6/-7). Compatible
  families to check for availability: ISSI IS42S16320, Alliance AS4C32M16SB, Micron
  MT48LC32M16A2. The current controller needs ≥ ~133-144 MHz (`docs/GATEWARE.md`).
* **MCU:** RP2040. Its PIO can drive the 4-bit microSD and an 8-bit parallel bus towards
  the FPGA; the C loader (`firmware/`) does not change. The alternative is an STM32 with
  SDMMC. Estimated load time (not measured): 4-bit SD about 10-20 MB/s, so 3-5 s for
  45 MiB.
* **FPGA configuration:** dedicated SPI NOR flash (not the MCU's).

## 4. 5 V ↔ 3.3 V level translators

Needed for all console signals (the FPGA is not 5 V tolerant). Proposed family: 16-bit
dual-supply translators (`74LVC16T245` class, TSSOP-48): FPGA side 3.3 V, console side 5 V,
DIR pin driven by the FPGA for the 40 bidirectional ones (about 5 DIR pins), fixed for inputs
and outputs. With 22 groups of 8 bits that is about **11 parts** (AES; about 12 for the
MVS). Propagation delay of the order of a few ns per hop: to be put in the timing budget
after measurements on the console.

## 5. Power (estimate, not verified)

5 V arrives from the connector (`VCC` on pins 25-27 for the AES). We need at least 3.3 V
(FPGA I/O, SDRAM, MCU, FPGA-side translators), 2.5 V (ECP5 auxiliary) and 1.1 V (ECP5 core).
I do not know the current an AES slot can give a cartridge nor how much the design will
draw: **it must be measured** before choosing the regulators (and an inrush limiter may be
needed).

## 6. What is not decided and blocks the schematic

1. **Mechanics.** An AES cartridge is made of two boards (PROG and CHA) with 100 contacts
   each; I do not have the shell dimensions nor the relative position of the two
   connectors. Measurements from a real cartridge (or a shell) are needed to decide whether
   it is a single board with two combs or two linked boards (proposal in `docs/PCB.md`).
2. **Signal directions and levels** (`signals.csv`, `signals_mvs.csv`).
3. **5 V current** and start-up times with respect to the BIOS (`docs/BOOT.md`).
4. **Availability and price** of the chosen FPGA and SDRAM (not verified).
5. **KiCad schematic:** I have not generated it. There is no KiCad in this environment to
   validate it (ERC), and producing an unverifiable schematic with a 554-ball BGA would have
   little value; the next step is to do it with KiCad installed, starting from
   `hardware/signals.csv`, `hardware/signals_mvs.csv` and the AES footprints of the
   `neogeo-diag-kicad-library` library.
