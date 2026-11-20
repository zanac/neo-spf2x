# Board architecture (AES and MVS): proposal

KiCad is not available in this environment, so there is **no schematic or layout yet**: only
the partition, from which to design. Dimensions of the AES/MVS shell are not available (to be
measured on a specimen: wiki *Cartridge specifications*).

## Partition

Each cartridge is made of two boards, PROG and CHA, each with its own comb of contacts.
Proposal, the same for both formats:

| Board | Content |
|-------|---------|
| **CHA** | FPGA (ECP5 caBGA554), 64 MiB SDRAM (+ second footprint for 128 MiB), configuration flash, 5 V↔3.3 V translators for the CHA signals |
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

* `boards.py`: netlists of the four boards (AES/MVS × CHA/PROG) from `signals*.csv` and
  `*_pins.csv`; `build_sch.py` writes `hardware/out/*.kicad_sch`, `*_fpga_pins.csv` (net → ball)
  and `*_cha.lpf` (pin constraints), and checks every schematic by netlist round trip.
* `tests/test_hw_netlist.py`: every console signal must go finger → translator → FPGA ball
  (through the link for PROG), no ball used twice.

**Design choices in the netlist.** One 16-bit SN74ALVC164245 per two groups of 8 signals of
the same direction; bidirectional buses (`D0-15`, `SDRAD`, `SDPAD`, `SDD`) have a `DIR_*` net
driven by the FPGA; one `OE_*_N` per board, pulled up so that the translators are Hi-Z until
the FPGA is configured. The `DIR_*` nets have 10k pull-downs (SCAS416P "Power-Up Considerations", p. 7: VCCA first,
OE pulled up to VCCA, DIR low unless A→B is needed; the 5 V ramp of the console is unknown, check it on the bench). PROG and CHA are joined by two Hirose DF12 80-contact connectors, 0.5 mm pitch (receptacle
`DF12NB(3.0)-80DS-0.5V(51)` on CHA, plug `DF12NB(3.0)-80DP-0.5V(51)` on PROG; signals interleaved with
ground, 3.3 V from CHA, 5 V from both edges). SDRAM `CKE` is tied high. On the
MVS the PROG copies of `RESET`/`SLOTCS` are left unconnected (the CHA copies are used).
The second SDRAM shares the bus and has its own `SDR_CS1_N` (pulled up when the chip is not
fitted). FPGA I/O used: AES 215, MVS 235 of 245; the MVS needs 7 bank-8 balls that double as
configuration pins (last resort in `assign_balls`).

**Shell fit.** Outline, mounting holes and fingers come from the reference boards (jwestfall69,
public domain), thickness is 1.6 mm like those boards, all parts go on the front side. The gap
between PROG and CHA and the free height in the shell are not in any source I could reach (the
shop page needs a captcha). So the stack is made as low as the parts allow: the Hirose DF12NB(3.0)
pair is 3.0 +0.2 mm mated (Hirose drawing; the older DF12(3.0)-80DS/DP(86) are end of life since 2021 and
this is their compatible replacement; 0.3 A per contact, 50 cycles), so the two boards together are at most 6.4 mm
thick, instead of the 8.5 mm of 2×40 1.27 mm headers. `checks.py` verifies that
the PROG, turned over about a vertical axis, has its 160 link pads on the CHA pads with the same
number and net, that the mounting holes coincide, and that facing parts of the two boards add up
to less than 2.9 mm (worst case now 2.5 mm: FPGA under the RP2040). The footprints are generated from the Hirose land-pattern drawings (`hardware/gen/hirose_fp.py`):
pads 0.3 × 1.6 mm at 0.5 mm pitch, rows 2.0 mm apart, two 0.8 × 1.8 mm metal-fitting pads, 120 µm
stencil. The pad numbering is not on those drawings: it follows the stock KiCad library, so compare
it with the Hirose catalogue before ordering. Availability of the DF12NB parts was not checked. 0.3 A per contact is enough for the PROG supply (3 contacts of 3.3 V, 2 of 5 V).
Measure a real shell before ordering.

**Checked against datasheets (Nov 2026):** the SN74ALVC164245 TSSOP-48 pinout and supply
ranges (VCCA 2.3–3.6 V, VCCB 3–5.5 V, DIR high = A→B), the TLV62569 SOT-23-5 pinout
(VFB 0.6 V), the 54-pin x16 SDRAM pinout (Alliance AS4C32M16SB and ISSI IS42S16320D agree),
the ECP5 `CFG[2:0] = 010` Master SPI mode (TN1269 hardware checklist and the ECP5 PCIe board
guide), and the JTAG/flash/config balls against Lattice's pinout CSV. From the TN1269 checklist
the board now has 4.7k pull-ups on INITN, PROGRAMN, TDI, TMS, TDO, 4.7k pull-downs on TCK and
CCLK, and pull-ups on flash IO2/IO3. The JTAG header is the ARM Cortex Debug 10-pin 1.27 mm
connector (same pinout as the Tigard Cortex header; usable with J-Link and other probes
supported by openFPGALoader); nRESET (pin 10) is left unconnected.

**Checked against the primary datasheets supplied by the author** (kept in `datasheets/`): TLV62569,
ECP5 DS-02012 / TN-02039 (sysCONFIG) / TN-02038 (hardware checklist) / TN-02200 (PLL), W25Q128JV,
SN74ALVC164245 and SN74LVC16T245, AS4C32M16SB, RP2040 hardware design guide, Hirose DM3AT drawing, SD
Physical Layer Simplified Spec 9.10 and AMS1117 (no longer used). Errors found and fixed:

* the 3.3 V rail was a linear regulator (1.2 W in a SOT-223): now a TLV62569 buck, 0.6 × (1 + 453k/100k) = 3.32 V;
* the 2.5 V (VCCAUX) rail was fed from 3.3 V through a 1117 LDO with 0.8 V headroom, then from 5 V, which could
  rise before VCCIO (TN-02038 sec. 4 wants VCCIO first): it is now a third TLV62569 fed from the 3.3 V rail,
  0.6 × (1 + 316k/100k) = 2.496 V, so VCCIO, VCCAUX and VCC always start in that order;
* configuration pins (TN-02039 Table 4.5 / TN-02038 Table 6.2): CFG[2:0] = 010 with 4.7 kΩ pull-ups and 0 Ω straps
  for the zeros, MCLK 1 kΩ pull-up plus 33 Ω series, CSSPIN 4.7 kΩ, MOSI/MISO 10 kΩ pull-ups (they were wrong);
* FPGA decoupling per TN-02038 Table 3.1: 100 nF per VCC/VCCAUX/VCCIO ball, 3 × 10 µF on VCC, 10 µF per VCCIO bank,
  120 Ω ferrite + 10 µF on VCCAUX (the automatic placer does not guarantee one capacitor next to each ball: check by hand);
* the 24 MHz PLL reference is now on a dedicated PLL input ball (A2, `ULC_GPLL1T_IN`, TN-02200 sec. 7.1);
* SDRAM: CKE is driven by the FPGA, low at power-up, and DQM is held high until the 200 µs wait is over (note 11);
* unused translator channels are tied to GND on both sides (inputs are always active); the SN74ALVC164245 is kept
  because its 2 V VIH on the 5 V side accepts TTL and CMOS levels, while the SN74LVC16T245 needs 3.5 V (0.7 × VCCB);
  the ALVC is "not recommended for new designs" and wants VCCA before VCCB: to be reviewed;
* the RP2040 crystal is the ABM8-272-T3 of the Raspberry Pi guide (15 pF, 1 kΩ series).

Inductors (Taiyo Yuden catalogue, 2013): all three bucks use the NRS4018T2R2MDGJV (2.2 µH, shielded, 4.0 × 4.0 mm,
saturation current 3.0 A, temperature-rise current 2.2 A, DCR 42 mΩ); the catalogue land pattern (pads 1.2 × 3.7 mm, 2.8 mm
apart) is the one of the KiCad `L_Taiyo-Yuden_NR-40xx` footprint. With the TLV62569 formula (ΔIL = VOUT (1 − VOUT/VIN) / (L fSW),
IL,max = IOUT,max + ΔIL/2, saturation 20-30 % above) the 3.0 A part covers even the full 2 A rating of the regulator
(2.1 A × 1.3 = 2.7 A); with my estimated loads (about 1 A, 0.2 A and 0.5 A, not measured) a 1.65 A NRS4012 would also do.

microSD pull-ups: the SD specification (as reproduced in the Kingston microSD data sheet, Table 10) gives
10-100 kΩ for the CMD/DAT bus pull-ups (RCMD, RDAT) and the card draws at most 100 mA (150 mA SDXC) in default
speed and 200 mA in high speed; I changed the 47 kΩ to 10 kΩ (inside the range, the value Espressif also
prescribes), so the edges are faster. PCB vendor: the generator rules (0.1/0.1 mm track/space, 0.4/0.2 mm vias,
6 layers, 1.6 mm, ENIG because HASL is not offered on 6 layers) are inside the published capabilities of a
large low-cost vendor (JLCPCB: 0.09/0.09 mm, via 0.15/0.25 mm minimum, fill-and-cap vias in BGA pads by
default from 6 layers); the vendor you choose must be checked again.

Not verified: the dynamic supply currents (my estimate above), the pin-by-pin decoupling placement, the
shell dimensions, the pad numbering of the link connector and the vendor you actually use.

**Power budget (my estimate, not a measurement; the Lattice Power Calculator needs Diamond, not
available here).** From the data sheet (Table 3.8, typical at 85 °C): static ICC 116 mA at 1.1 V, ICCAUX 17 mA
at 2.5 V, ICCIO 0.5 mA per bank. SDRAM AS4C32M16SB: IDD4 124 mA, IDD5 160 mA, standby IDD3N 70 mA (one active
chip plus the optional second in standby: 230 mA). Dynamic FPGA, rough: core at 132 MHz with ~1300 flip-flops
and activity 15-25 % about 0.1 A at 1.1 V (guess), I/O about 0.15 A at 3.3 V worst case (CV²f with 10-15 pF).
Others from memory, not checked: flash 25 mA, RP2040 30 mA, microSD 100-200 mA. Worst case on 3.3 V about
0.8 A, i.e. about 0.6 A from the 5 V (efficiency 90 %); the TLV62569 gives 2 A (switching 1.5 MHz), the
inductor ripple is about 0.34 A (3.3 V from 5 V, 2.2 µH), peak about 1 A against Isat 3.0 A, and the 1.1 V rail
about 0.3 A. So the buck converters and the inductor have a factor of 2 or more of margin; the load on the
console's 5 V is the number to check against what the slot can supply (unknown, to be measured).

**Mechanical registration, checked on the reference boards (jwestfall69 KiCad files):** both
PROG and CHA have two 10 mm mounting holes 90 mm apart, at the same position relative to the
contact fingers (46.27 mm to the left of finger A on both). In the AES the PROG origin is shifted
by (13.29, 1.65) mm from the CHA one, in the MVS by (15.08, 1.65) mm, the same numbers as for
the fingers. The PROG is stacked turned over about a vertical axis (the boards are nearly mirror-symmetric:
bounding boxes aligned after the flip, outlines differ by less than 1 % of the area, holes
coincide within 0.01 mm), so its link connectors are placed mirrored, and `hardware/gen/checks.py` checks that every part lies inside the real outline (notches
included) and clear of the holes. What remains unknown is the gap between the boards in the
shell (below).

**microSD slot:** in the Hirose DM3AT footprint the contacts are on the −y side and the card
enters from +y; the slot is rotated 180° so that it opens towards the top edge of the PROG,
the edge opposite the fingers. The slot is flush with the top edge of the outline (the opening on the edge, `prog_anchors` in `build_pcb.py`);
a cut-out in the shell is still needed (design choice, not verified on a real shell).

**SDRAM (AS4C32M16SB datasheet):** see `docs/GATEWARE.md`.

**BGA footprint, checked against Lattice FPGA-DS-02053 v8.8 (caBGA554):** body 23.0 × 23.0 mm,
26 × 26 balls at 0.80 mm pitch (20.0 mm square), ball 0.40 mm nominal (0.35–0.45), row letters
A–AF without I, O, Q, S, X, Z, maximum package height 1.76 mm. The package datasheet gives no land size, but Lattice TN-02024 v4.1 does: for the 554 caBGA the
recommended PCB land is 0.400 mm NSMD (0.500 mm solder-mask opening if SMD), against a 0.300 mm
opening on the package side, which is the 0.4 mm pad used here. TN-02024 also shows a 554-ball breakout in
4 layers with 4 mil (0.10 mm) traces and 7 mil (0.18 mm) via drills; this design uses 6 layers, 0.1/0.1 mm
rules and 0.2 mm drills. The assembler still has to confirm the process.

**Still not verified:** the real
height and gap in the shell, all dynamic supply currents (the data sheet gives static ones only;
the Lattice Diamond power calculator is needed), the 5 V draw from the console, the inductor
saturation current of the core buck, and the MVS hypotheses of `docs/MVS.md`.

**Status:** schematics and netlists done for the four boards, with ball assignment. Placement
is done and geometry-checked (`checks.py`, `fanout.py` for the BGA); autorouting, DRC and Gerbers are not
done yet. Anything generated needs a human design review
before fabrication.
