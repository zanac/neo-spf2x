# AES connector pinout (PROG and CHA boards)

**Source:** KiCad symbols of jwestfall69's `neogeo-diag-aes-prog` project and its
`neogeo-diag-kicad-library` (both public domain), extracted automatically from the
`.kicad_sym` files: no hand transcription. Sides and pin numbers are those of the
symbols in that library.

**Status:** these are signal names and pin numbers, **not** an electrical
specification. Directions, timings and levels are missing. Before sending a PCB to
production they must be checked against a real AES cartridge (continuity with a
multimeter) and against the *Signal names* page of the neogeodev wiki.

An AES cartridge is made of two boards side by side, PROG and CHA, each with 50
contacts per side (100 per board, 200 in total, as reported by the wiki). To fit an
AES shell, our cartridge must present both connectors.

## Contact geometry

From the footprint `neogeo-aes-a-side-edge`: 50 contacts at 2.54 mm pitch, each
1.5 × 10 mm. Board thickness 1.6 mm; the repo suggests ENIG finish and gold fingers
with a 45° chamfer. The repo's PROG board has two copper layers.

## Power and shared lines

`VCC` on pins 25, 26, 27 of both sides and `GND` on pins 1, 2, 49, 50.
`L_OUT/L_IN` and `R_OUT/R_IN` are pins 23 and 24 of both boards (A: L, B: R): in the
repo's PCB they are on the same net (`L_AUDIO`, `R_AUDIO`), i.e. the audio makes a
loop through the cartridge and must be closed again.

## Board PROG

| Pin | Side A | Side B |
|----:|--------|--------|
| 1 | GND | GND |
| 2 | GND | GND |
| 3 | D0 | A1 |
| 4 | D1 | A2 |
| 5 | D2 | A3 |
| 6 | D3 | A4 |
| 7 | D4 | A5 |
| 8 | D5 | A6 |
| 9 | D6 | A7 |
| 10 | D7 | A8 |
| 11 | D8 | A9 |
| 12 | D9 | A10 |
| 13 | D10 | A11 |
| 14 | D11 | A12 |
| 15 | D12 | A13 |
| 16 | D13 | A14 |
| 17 | D14 | A15 |
| 18 | D15 | A16 |
| 19 | R/W | A17 |
| 20 | AS | A18 |
| 21 | ROMOEU | A19 |
| 22 | ROMOEL | ROMOE |
| 23 | L_OUT | R_OUT |
| 24 | L_IN | R_IN |
| 25 | VCC | VCC |
| 26 | VCC | VCC |
| 27 | VCC | VCC |
| 28 | PORTOEU | ROMWAIT |
| 29 | PORTOEL | PWAIT1 |
| 30 | PORTWEU | PWAIT0 |
| 31 | PORTWEL | PDTACK |
| 32 | 68KCLKB | SDRAD0 |
| 33 | RESET | SDRAD1 |
| 34 | SDPAD0 | SDRAD2 |
| 35 | SDPAD1 | SDRAD3 |
| 36 | SDPAD2 | SDRAD4 |
| 37 | SDPAD3 | SDRAD5 |
| 38 | SDPAD4 | SDRAD6 |
| 39 | SDPAD5 | SDRAD7 |
| 40 | SDPAD6 | SDRA8 |
| 41 | SDPAD7 | SDRA9 |
| 42 | SDPA8 | SDRA20 |
| 43 | SDPA9 | SDRA21 |
| 44 | SDPA10 | SDRA22 |
| 45 | SDPA11 | SDRA23 |
| 46 | SDPMPX | SDRMPX |
| 47 | SDPOE | SDROE |
| 48 | PORTADRS | 4MB |
| 49 | GND | GND |
| 50 | GND | GND |

Groups: 68k data bus `D0-D15`, address bus `A1-A19`, control (`R/W`, `AS`, `ROMOE`,
`ROMOEU/L`, `PORTOEU/L`, `PORTWEU/L`, `PORTADRS`, `68KCLKB`, `RESET`), waits
(`ROMWAIT`, `PWAIT0/1`, `PDTACK`), ADPCM buses (`SDPAD0-7`, `SDPA8-11`, `SDPMPX`,
`SDPOE` and `SDRAD0-7`, `SDRA8-9`, `SDRA20-23`, `SDRMPX`, `SDROE`) and `4MB`.

## Board CHA

| Pin | Side A | Side B |
|----:|--------|--------|
| 1 | GND | GND |
| 2 | GND | GND |
| 3 | PCK1B | FIXD0 |
| 4 | PCK2B | FIXD1 |
| 5 | 12M | FIXD2 |
| 6 | 2H1 | FIXD3 |
| 7 | EVEN | FIXD4 |
| 8 | H | FIXD5 |
| 9 | LOAD | FIXD6 |
| 10 | CA4 | FIXD7 |
| 11 | P0 | P1 |
| 12 | P2 | P3 |
| 13 | P4 | P5 |
| 14 | P6 | P7 |
| 15 | P8 | P9 |
| 16 | P10 | P11 |
| 17 | P12 | P13 |
| 18 | P14 | P15 |
| 19 | P16 | P17 |
| 20 | P18 | P19 |
| 21 | P20 | P21 |
| 22 | P22 | P23 |
| 23 | L_OUT | R_OUT |
| 24 | L_IN | R_IN |
| 25 | VCC | VCC |
| 26 | VCC | VCC |
| 27 | VCC | VCC |
| 28 | SDRD0 | NC |
| 29 | SDRD1 | NC |
| 30 | SDA0 | DOTA |
| 31 | SDA1 | DOTB |
| 32 | SDA2 | GAD0 |
| 33 | SDA3 | GAD1 |
| 34 | SDA4 | GAD2 |
| 35 | SDA5 | GAD3 |
| 36 | SDA6 | GBD0 |
| 37 | SDA7 | GBD1 |
| 38 | SDA8 | GBD2 |
| 39 | SDA9 | GBD3 |
| 40 | SDA10 | SDD0 |
| 41 | SDA11 | SDD1 |
| 42 | SDA12 | SDD2 |
| 43 | SDA13 | SDD3 |
| 44 | SDA14 | SDD4 |
| 45 | SDA15 | SDD5 |
| 46 | SDMRD | SDD6 |
| 47 | SDROM | SDD7 |
| 48 | 24M | 8M |
| 49 | GND | GND |
| 50 | GND | GND |

Groups: **address inputs** `P0-P23` (split between the two sides: even on side A,
odd on side B) with `CA4`, `PCK1B`, `PCK2B`, `2H1`, `12M`, `LOAD`, `EVEN`, `H`,
`8M`, `24M`; **pixel outputs** `DOTA`, `DOTB`, `GAD0-3`, `GBD0-3`; **fix data**
`FIXD0-7`; **Z80 bus** `SDA0-15`, `SDD0-7`, `SDRD0/1`, `SDMRD`, `SDROM`.
`NC` are unconnected pins.

## What it implies for the project

* On the CHA the AES connector **does not carry the C ROM data** (no `CR` pin appears
  in the symbols, in line with the wiki on NEO-ZMC2): it carries the tile address
  (`P0-P23`) and expects already-serialized pixels back (`DOTA/DOTB`, `GAD`, `GBD`)
  and the fix layer data (`FIXD0-7`). The work of the PRO-CT0 chip therefore falls
  entirely on our FPGA.
* The Z80 bus (`SDA`, `SDD`, `SDMRD`, `SDROM`) is on the connector: we must serve the
  M ROM and the bank switching that NEO-ZMC does.
* The PROG has `ROMWAIT`, `PWAIT0/1` and `PDTACK`: these are the candidates to hold
  the console still while loading from SD. Function and polarity still have to be
  verified.
