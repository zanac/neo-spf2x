# Protected games and special cartridges: what each one needs

Source: MAME (`src/devices/bus/neogeo/`, `src/mame/snk/neogeo.cpp`, `hash/neogeo.xml`) read
on 2026-11-20, plus the NeoGeo_MiSTer core (`neo_cmc.v`, `neo_pvc.v`, `neo_sma.sv`) for the
fix-layer banking. Nothing here is measured on hardware. `tools/mame_census.py` reproduces the
numbers from MAME's software list.

## 1. What the software list says

307 sets (originals and bootlegs).

| Item | Result |
|------|--------|
| Plain cartridge (`rom` slot) | 225 sets |
| Sets using a special chip or logic | 82 sets (28 of them bootlegs) |
| Largest set | 90 MiB (P 9, C 64, V 16, S 0.5, M 0.5) |
| Sets above 64 MiB | 77 |
| Sets that fit the `ngsd-64M` profile | 188 |
| Sets with C above 38 MiB | 90 |
| Sets with P above 8 MiB | 24 |
| Sets with a separate ADPCM-B ROM (VB, up to 2 MiB) | 21 |

Conclusion: **128 MiB of SDRAM covers every set** (profile `ngsd-128M`: two 64 MiB chips, CS
chosen by address bit 26). The board has the second footprint and its `CS` line.

## 2. Three kinds of work

* **Pack time (PC, no hardware):** the chips that only scramble data. CMC42/CMC50 (C, S and
  M1 decryption, S extracted from C), PCM2 (V), the static P scrambles (SMA, KOF2002, PVC
  families, KOF98) are permutations done once by `tools/ngpk.py`. The `.ngpk` then holds plain
  data and needs mapper 0.
* **Runtime logic in the FPGA (no PCB change):** everything below lives on the buses the FPGA
  already sees (P bus, `D`, `ROMOE`, `PORTOE`, `PORTWE`, the wait lines).
* **Not understood well enough yet:** listed in section 4.

## 3. Runtime logic per family

| MAME slot | Games | What the cartridge does at run time |
|-----------|-------|-------------------------------------|
| `rom` | 225 sets | P bank latch at `$2FFFF0` (done) |
| `rom_fatfur2` | Fatal Fury 2 | reads/writes in `$2xxxxx` go through a PRO-CT0 (the same chip family as the sprite serializer): needs a model of that chip |
| `rom_kof98` | KOF 98 | a write of `$0090` to `$20AAAA` makes reads of `$100-$103` return `$00C200FD`, a write of `$00F0` makes them return `$4E454F2D`: a two-state overlay |
| `rom_mslugx` | Metal Slug X | commands at `$2FFFE0-$2FFFEF`, serial bits taken from P ROM at `$DEDD2`; MAME reads the 68k work RAM `$10F00A` for one command, which a cartridge cannot see: unverified |
| `sma_*` | KOF 99, Garou, Metal Slug 3, KOF 2000 | bank register (`$2FFFF0`, `$2FFFC0`, `$2FFFE4`, `$2FFFEC`) through a 64-entry table of a scrambled 6-bit value, a random number generator read at `$2FE446` and other addons |
| `pvc_*` | Metal Slug 5, SvC Chaos, KOF 2003 | 8 KiB RAM at `$2FE000-$2FFFFF`; writes to words `$FF0`, `$FF4-$FF5` (bytes `$2FFFE0-$2FFFEB`) trigger colour unpack/pack, `$FF8-$FF9` hold a P bank address. Small |
| `cmc42_*`, `cmc50_*`, `pcm2_*`, `k2k2_*` | about 28 games | data decryption at pack time (see above), plus fix-layer banking, below |
| `cmc50_jockeygp`, `rom_vliner` | Jockey GP, V-Liner | 8 KiB RAM at `$200000-$201FFF` (battery-backed on the original; V-Liner also needs console inputs a cartridge does not have) |
| `boot_*` | 28 bootlegs | each its own logic; lowest priority |

**Fix-layer banking.** 23 carts use type 1 (Garou, Metal Slug 3/4/5, KOF 99, KOF 2001,
Samurai Shodown V, Rage of the Dragons and others) and 5 use type 2 (KOF 2000 and 2000N,
Matrimelee, SvC, KOF 2003). The S ROM is up to 512 KiB and the chip selects a 128 KiB bank per
group of screen lines or tile columns, from information the game stores in video RAM (`$7500-$75FF`). MAME and MiSTer read it from the video
RAM address; the cartridge only sees the words the LSPC puts on the P bus.

## 4. Open risks

* Fix banking: the cartridge cannot see the VRAM address. `neo_cmc.v` uses it. Whether the same
  state can be rebuilt from the `PCK2B` stream alone is not shown by the sources I read. About 28
  original games depend on it. It needs a logic analyzer capture or a PRO-CT0/CMC schematic.
* Metal Slug X (one game) and SBP (a bootleg) have undocumented protections.
* Timing: every `$2xxxxx` read must be answered inside the 68k cycle (`PWAIT`/`PDTACK` lines exist).
* Nothing runs yet: the mapper field of the format is the hook, the gateware modules do not exist.

## 5. Proposed order of work

1. Pack-time decryptions in `tools/ngpk.py` (CMC, PCM2, SMA, KOF2002, PVC, KOF98), each tested
   against MAME's decrypted output when ROM sets are available.
2. Gateware: SMA bank/RNG, PVC RAM, KOF98 overlay (small modules, testable in simulation).
3. Fix-layer banking, after a capture of real PCK1B/PCK2B traffic.
4. PRO-CT0 and Metal Slug X.
5. Bootlegs on request.
