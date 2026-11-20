# Neo Geo AES/MVS cartridge with microSD: format, packer, loader and gateware

🇬🇧 English · [🇮🇹 Italiano](README.it.md)

A Neo Geo cartridge (AES and MVS) that loads a game from a microSD card. The software side
(format, packer, loader) is written and tested; the FPGA gateware is simulated but not proven
on a console; the PCBs are not designed yet (the partition is in `docs/PCB.md`). See
`docs/ARCHITECTURE.md` for the status and the open points.

**Documentation is kept in English (`docs/`, this README) and in Italian (`docs/it/`,
`README.it.md`), and both versions are updated together** (`tests/check_docs.py`).

## Contents

| Path | What |
|------|------|
| `docs/FORMAT.md` | Specification of the `.ngpk` format and of the recipes |
| `docs/MVS.md`, `docs/PCB.md` | MVS/AES differences, MVS pinout and board partition (AES + MVS) |
| `docs/AES_PINOUT.md` | Signal names and pin numbers of the AES PROG and CHA connectors |
| `docs/TIMING.md` | Sprite, fix, bank switching and NEO-ZMC behaviour derived from Geolith, with what is missing |
| `docs/ARCHITECTURE.md` | Architecture, SDRAM map, contract with the FPGA, open points |
| `tools/ngpk.py` | Packer/inspector (Python 3, no dependencies) |
| `recipes/` | Recipes: Samurai Shodown III (example) and `spf2ng` (the project's game) |
| `docs/GATEWARE.md` | Status of the Verilog gateware and what the tests prove |
| `gateware/` | RTL and testbenches (Icarus Verilog): sprite (AES and MVS), fix, P bank, Z80 bank, SDRAM controller, arbiter, top |
| `docs/BOOT.md` | How the console sees the cartridge during loading (boot stub) |
| `boot/` | 68k source of the stub (`stub.S`) and binary |
| `docs/PROTECTIONS.md` | Protected games and special cartridges (from MAME): what each needs, 128 MiB, open risks |
| `docs/COMPONENTS.md` | I/O budget, choice of FPGA, SDRAM, MCU, translators and open hardware points |
| `hardware/` | `gen_signals.py`, `signals.csv` (162 AES signals), `signals_mvs.csv` (184 MVS pins), `mvs_pins.csv`, `extract_kicad_pins.py` |
| `firmware/` | `.ngpk` parser and loader in portable C99, plus PC tests |
| `tests/` | Packer tests, documentation check and the script that runs everything |

ROM files are not included: you need your own dumps.

**License:** GPL-3.0-or-later, text in `LICENSE`.

## Usage

```sh
# create a package (the recipe lists the files, --base-dir says where they are)
python3 tools/ngpk.py pack recipes/samsho3.json --base-dir /path/to/romset -o samsho3.ngpk

python3 tools/ngpk.py info   samsho3.ngpk    # regions, sizes, CRC
python3 tools/ngpk.py verify samsho3.ngpk    # re-check the CRCs
python3 tools/ngpk.py unpack samsho3.ngpk -o out/   # P.bin, C.bin, ...
# unpack --canonical brings C and S back to MAME order; pack uses the sdram1 layout (docs/FORMAT.md)

# tests (without ROMs it uses a synthetic game; with a folder it also uses the romset)
tests/run_all.sh
tests/run_all.sh /path/to/romset
```

Copy the `.ngpk` files onto the microSD: the loader reads them through the MCU's file system
(FatFS).

## Adding a game

Write a recipe (see `docs/FORMAT.md`): which files go in which region and with which
operation (`concat`, `swap16`, `interleave8`). The packer checks that `NEO-GEO` is at `0x100`
of the P, so a wrong swap does not go unnoticed. Games requiring protections or encryption
(SMA, PCM2, CMC, PVC...) are not supported yet and are rejected.

## Porting the loader to an MCU

`firmware/ngsd_loader.c` does not depend on the hardware. Four functions in `ngsd_hal_t` are
implemented: reading from the file on the SD (FatFS), writing into SDRAM through the FPGA,
writing the FPGA registers and, if needed, a progress bar. The code compiles with `-std=c99`
without libraries.
