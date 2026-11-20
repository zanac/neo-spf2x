# MVS cartridge: differences from the AES and project status

**Request:** PCBs for both AES and MVS. This document summarizes what changes and what is
already in the repo. The two formats **cannot** be covered with a single connector
(different geometry and pinout): two sets of boards are made, with the same logic (FPGA,
SDRAM, MCU, microSD, firmware).

**Source of the pinouts:** KiCad symbols of `jwestfall69/neogeo-diag-mvs-prog` and
`neogeo-diag-mvs-cha` (public domain), extracted with `hardware/extract_kicad_pins.py` into
`hardware/mvs_pins.csv` (240 pins). The neogeodev wiki has the MVS pinouts only as images;
the wiki gives 60 contacts per side, 120 per board, 2.54 mm pitch, 1.6 mm thickness, and
warns that elsewhere `/ROMOE` and `4MB` are swapped: `/ROMOE` is pin 33 on side B, `4MB` is
pin 34 on side B (consistent with the extracted symbols). **As for the AES: names and
numbers, not an electrical specification**; directions deduced from the names
(`hardware/signals_mvs.csv`).

## 1. Differences that matter

| Aspect | AES | MVS |
|--------|-----|-----|
| Contacts | 50 per side, 100 per board | 60 per side, 120 per board |
| Console-side signals | 162 | **184 pins, 182 signals** |
| Sprite data towards the console | serialized by the NEO-ZMC2 in the cartridge: `GAD0-3`, `GBD0-3`, `DOTA`, `DOTB` (+ `LOAD`, `H`, `EVEN`, `12M`) | **parallel: `CR0-CR31`** (32 bits); the serializer is in the console |
| Clocks | `12M` | `24M`, `12M`, `8M` |
| Slot selection | – | `SLOTCS` (several cartridges on the common backplane: outputs must be kept high-impedance when `SLOTCS` is not active) |
| 68k strobes | bus addresses/strobes | `ROMOEU/L`, `PORTOEU/L`, `PORTWEU/L` (high/low byte), `PORTADRS`, `AS`, `R/W`; only `A1-A19` on the connector |
| ADPCM | multiplexed `SDPAD`/`SDRAD` buses | same buses, with `SDPA8-11`, `SDPMPX`, `SDPOE` and `SDRA8-9`, `SDRA20-23`, `SDRMPX`, `SDROE` |
| Z80/M ROM | `SDA`, `SDRD0/1`, `SDMRD`, `SDROM` | same |

On the MVS the gateware is **simpler** on the sprite side: it just answers with 32 bits on
`CR` to the address latched by `PCK1B`, choosing the half with `CA4`. The `P0-P23` bus and
`FIXD0-7` are unchanged (the fix uses `PCK2B` and `2H1`).

## 2. What is in the repo

* `gateware/rtl/ng_cfetch_mvs.v`: C fetch without the serializer, `cr = CA4 ? half2 :
  half1` (same `sdram1` layout, no change to the `.ngpk` format or to the loader).
* `gateware/rtl/ng_mvs_pdec.v`: from `ROMOE*/PORTOE*/PORTWE*` + `A1-A19` to the
  address/strobe interface of `ng_pbank` (unchanged).
* `ng_top` has the parameter `MVS` (0 = AES, 1 = MVS) and the output `cr[31:0]`.
* `gateware/tests/test_mvs.py`: self-checking testbench (40 tile rows, two halves, three
  68k accesses) plus elaboration of `ng_top` with `MVS=0/1`. `tests/run_all.sh` → ALL OK.
* `hardware/signals_mvs.csv`: 184 pins with deduced direction.

## 3. **Unverified** hypotheses specific to the MVS

1. The mapping `ROMOE`/`PORTOE`/`PORTWE` → regions `$000000` / `$200000`
   (`ng_mvs_pdec.v`). The exact meaning of `PORTADRS` is not used.
2. Which 4-byte half corresponds to `CA4 = 0` and the bit order on `CR` (same hypothesis as
   the AES, still unproven on hardware).
3. The deadline between `PCK1B` and the console sampling `CR`.
4. The boot stub (`docs/BOOT.md`) was designed for the AES: the MVS boot logic (different
   BIOS, no AES menu) must be verified; `ROMWAIT`/`PWAIT`/`PDTACK` have the same names.
5. **The MVS ADPCM bus is not implemented** (as for the AES: generic `v_rd`/`v_offs`, the
   link with the multiplexed buses is missing). It is needed for games with speech.
6. `RESET` (pin 35 side B PROG and pin 18 side B CHA), `4MB` and `SLOTCS`: direction and
   use.

## 4. Effects on I/O and components

182 console signals + 39 SDRAM + ≥ 6 MCU link (SPI) + ~6 misc ≈ **233-241**: on the ECP5
LFE5U-45F caBGA554 (245 I/O) at most ~12 pins are left. It fits the 45F, with little margin
(the SDRAM control pins that the design does not use are tied off). The **LFE5U-85F in the same
caBGA554** (259 I/O, same footprint) is a drop-in fallback: on the same PCB one or the other is fitted. Details in `docs/COMPONENTS.md` and board architecture
in `docs/PCB.md`.
