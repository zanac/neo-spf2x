# Board architecture (AES and MVS): proposal

KiCad is not available in this environment, so there is **no schematic or layout yet**: only
the partition, from which to design. Dimensions of the AES/MVS shell are not available (to be
measured on a specimen: wiki *Cartridge specifications*).

## Partition

Each cartridge is made of two boards, PROG and CHA, each with its own comb of contacts.
Proposal, the same for both formats:

| Board | Content |
|-------|---------|
| **CHA** | FPGA (ECP5 caBGA554), 64 MiB SDRAM, configuration flash, 5 V↔3.3 V translators for the CHA signals |
| **PROG** | translators for the PROG signals, RP2040, microSD slot, LED/button |
| Link | 3.3 V board-to-board between PROG and CHA (about 83 PROG signals + SPI/power) |

The PROG signals (A1-A19, D0-D15, strobes, ADPCM) must reach the FPGA: hence the link. With
the FPGA on a single board no translators are needed on the bridge.

## Board sets

* **AES:** comb of 50 contacts per side (162 signals): `AES_PINOUT.md`, `signals.csv`.
* **MVS:** comb of 60 contacts per side (182 signals): `MVS.md`, `signals_mvs.csv`.
* Same logic; only the two combs, the translator block (number of lines) and `MVS` in the
  gateware (parameter of `ng_top`) change.

## To do in KiCad (in order)

1. Schematic: FPGA with 3.3 V I/O banks, SDRAM, translators (~12 16-bit for the MVS, ~11 for
   the AES), RP2040, microSD, power from the connector's `VCC` (5 V).
2. Comb footprints from the `neogeo-diag-kicad-library` library (AES:
   `neogeo-aes-*-side-edge`; MVS: the symbols already used in `mvs_pins.csv`).
3. 6-8 layer layout with controlled-impedance SDRAM, ENIG finish, 45° chamfer.
4. Verification against a real cartridge before production (continuity and directions), 5 V
   draw, outputs held high-Z with `SLOTCS` (MVS) and during FPGA configuration.

## Hardware generator (`hardware/gen/`)

KiCad 7 files are generated from scripts, so that the boards follow the pin tables.

* `fpga_db.py`: ball database and BGA554 footprint from the official Lattice CSV
  (`hardware/fpga/`).
* `design.py`, `kisch.py`: netlist model and schematic writer; `selftest_sch.py` checks that
  the generated schematic exports to the same netlist (KiCad 7's CLI has no ERC).
* Board outlines and edge fingers come from `hardware/outline.json` and `hardware/footprints/`.

**Status:** schematic writer and FPGA footprint done; board netlists, placement, routing and
DRC for AES/MVS × CHA/PROG are not done yet. Anything generated needs a human design review
before fabrication.
