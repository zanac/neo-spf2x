# Gateware (status)

Generic Verilog, no vendor primitives. Simulation with Icarus Verilog (`iverilog`,
`vvp`); the tests only run if `iverilog` is installed.

## Modules

| File | What it does |
|------|--------------|
| `gateware/rtl/ng_cfetch.v` | Sprites (AES): captures the address from the `P` bus on `PCK1B`, reads the tile row from the SDRAM (8 bytes, a single read) and serializes it at 2 pixels per `12M` tick, with `H` for the flip |
| `gateware/rtl/ng_cfetch_mvs.v` | Sprites (MVS): same fetch, no serializer; drives `CR0-CR31` with `CA4` choosing the 32-bit half (`docs/MVS.md`) |
| `gateware/rtl/ng_sfetch.v` | Fix layer: captures tile/position on `PCK2B`, reads 8 bytes, `S2H1` chooses the byte for `FIXD0-7` |
| `gateware/rtl/ng_pbank.v` | 68k: P read (fixed P1 + 1 MiB window) and bank latch, cleared at reset |
| `gateware/rtl/ng_mvs_pdec.v` | MVS: `ROMOE*/PORTOE*/PORTWE*` + `A1-A19` → address/strobe interface of `ng_pbank` |
| `gateware/rtl/ng_zmc.v` | Z80: M ROM bank switching (4 windows, 512 KiB reach, identity map at reset) |
| `gateware/rtl/ng_boot.v` | 1 KiB boot RAM served to the 68k in stub mode (`docs/BOOT.md`), written by the MCU, preloadable from `BOOT_HEX` |
| `gateware/rtl/ng_adpcm.v` | YM2610 ADPCM bus snooper (parameter `B`: 0 = A, 1 = B): rebuilds the 24-bit address from the multiplexed `SDRAD/SDPAD` lines (`docs/TIMING.md` §11), reads the byte from the V region and drives the data bus while `SDROE/SDPOE` is low; `late` counts missed deadlines |
| `gateware/rtl/ng_mcu_spi.v` | SPI slave towards the MCU (1-bit or quad write): register writes, run flag, and a window on the MCU SDRAM port; reads are limited to clk/8 by the synchroniser latency |
| `gateware/rtl/ng_rdport.v` | Byte read from a region (M port and V port of the ADPCM data, abstract) |
| `gateware/rtl/ng_sdram.v` | 16-bit SDR SDRAM controller, 4 banks, CL3, burst 4, closed page, one request at a time; init and refresh; up to two chips (`sd_cs_n[1:0]`, chip = `addr[26]`) |
| `gateware/rtl/ng_arb.v`, `ng_fifo4.v` | Fixed-priority arbiter MCU > C > S > P > M > V with a 4-request FIFO per port |
| `gateware/rtl/ng_top.v` | Integration: MCU registers (the map of `firmware/ngsd_loader.h`), tile masks derived from `SIZE_x`, bases from `ADDR_x`, MCU SDRAM port, boot RAM and stub mode; parameter `MVS` (0 = AES, 1 = MVS) and output `cr[31:0]` |
| `gateware/tb/` | Testbenches and behavioural SDRAM model with timing and refresh checks |
| `gateware/model/` | `sdram_budget.py` (ideal Python model) and `rtl_budget.py` (stress on the RTL) |

Not written yet: physical interface towards the MCU (SPI/QSPI), real ADPCM (`SDPAD/SDRAD`
buses, AES and MVS), wait handling (`ROMWAIT`, `PDTACK`), pin and timing constraints,
SDRAM controller with bank interleaving, MVS multi-slot tri-state control (`SLOTCS`).

## How to test

```sh
python3 gateware/tests/test_cfetch.py                # sprite serializer, random data
python3 gateware/tests/test_cfetch.py C_canonical.bin # same with real data (MAME order)
python3 gateware/tests/test_modules.py               # fix, P bank, Z80 banking
python3 gateware/tests/test_system.py                # everything together with controller and SDRAM chip
python3 gateware/tests/test_sdram2.py                # two SDRAM chips (ngsd-128M)
python3 gateware/tests/test_mvs.py                   # MVS: CR fetch, P strobes decoder, ng_top MVS=0/1
python3 gateware/model/rtl_budget.py                 # peak traffic on the RTL, latencies
```

`tests/run_all.sh` runs them if `iverilog` is installed.

The test converts the canonical data to the `sdram1` layout with `tools/ngpk.py`, loads
it into the testbench's SDRAM model and compares, for 400 random tile rows (with and
without `H`, 20-bit tile numbers that fold back onto the C ROM size), every output pixel
with the canonical decoding model written following Geolith. It also tries three
combinations of SDRAM latency and `LOAD` lead; the last is a negative test that must
report underrun. Current result: **0 wrong pixels** with random data and with a real
portion of the `spf2ng` sprites.

## What it proves and what it does not

It proves that the `sdram1` permutation and the serializer together return the same
pixels as the reference decoder, and that the logic holds the data flow under the
hypotheses below. It does **not** prove that it matches a real console.

Model choices not verified on hardware:

* `CA4 = 0` selects the first 4 bytes of the row (the canonical `+0x40` half).
* At every `12M` tick a pair `(gad, gbd)` = (previous pixel, following pixel) comes out
  in time order; `EVEN` is not used. On a real cartridge `EVEN` and `H` decide which bits
  form the pair: to check.
* `LOAD` is sampled on a `12M` tick modelled as a fast-clock pulse; the real polarity and
  edge of `12M` are an open point.
* The C ROM size is a power of two (`tile_mask`); for other sizes a real modulo module is
  needed, which Geolith applies with `%`.
* In the serializer-only test the SDRAM model has fixed latency; the behaviour with a real
  SDRAM and controller is in the section "Measurement on the RTL" (below), which is still a
  simulation.
* MVS: the same `CA4` hypothesis, the assignment of `ROMOE`/`PORTOE`/`PORTWE` to the 68k
  regions and the `CR` sampling deadline (`docs/MVS.md`).

## SDRAM budget (model, `gateware/model/sdram_budget.py`)

It is not RTL: it is a cycle-level scheduler of a 16-bit SDR SDRAM (4 banks, closed page
with auto-precharge, parameters like 133 MHz CL3 with tRCD 20 ns, tRC 64 ns, refresh every
7.8 µs) that serves together the worst traffic the console can generate, with the
frequencies derived from `docs/TIMING.md`:

| Class | Traffic | Model |
|-------|---------|-------|
| C | 8-byte sprite row every 667 ns (96 sprites per line, 100 % duty) | random addresses in 32 MiB |
| S | two 16-bit reads every 667 ns | random in 128 KiB |
| P | one 16-bit read every 333 ns (68k at 12 MHz) | sequential |
| M | one byte every 750 ns (Z80 at 4 MHz) | random |
| V | ADPCM-A (6 channels) + ADPCM-B | random |

Result over 4 ms simulated (bank mapping "top" = 16 MiB per bank, or "interleave" = 2 KiB
interleaved pages; C-first or P-first priority):

* data bus usage **10 % at 133 MHz, 14 % at 100 MHz**: bandwidth is not the problem;
* worst latency (arrival → last data) on C reads **173-241 ns at 133 MHz, 240-270 ns at
  100 MHz**; p99 135-150 ns; P and S similar, M and V up to 390 ns;
* no accumulation of queued requests.

**What it means and what not.** The SDRAM holds the peak traffic with ample bandwidth
margin. What the model cannot say is whether 170-270 ns are enough: it depends on the
distance between `PCK1B` and the `LOAD` that uses the data, which I do not know (open
point, to be measured). A hint: the NeoGeo_MiSTer core serves the C ROMs from a 120 MHz
SDRAM, so the real deadline is compatible with latencies of this order, but this is a
deduction from how it works, not a measurement. The model also neglects clock-domain
synchronizers, 5 V translator delays, fine tRAS/precharge on command changes and the real
controller arbitration: it must be redone on the RTL controller when it exists. The choices
that remain useful: 133 MHz SDRAM (not 100) to have more margin on the worst-case latency,
priority to C and S over the rest.

## Measurement on the RTL (`gateware/model/rtl_budget.py`)

Same peak traffic as the table above, but on the real RTL (`ng_top` + `ng_sdram` +
behavioural chip with timing checks), 2 ms simulated. The current controller executes
**one request at a time** and does no bank interleaving, so it is worse than the ideal
model.

| SDRAM clock | Sprite, max / mean latency | Fix | 68k (P) | Z80 (M) | V | Notes |
|-------------|----------------------------|-----|---------|---------|---|-------|
| 144 MHz | 285 / 138 ns | 285 ns | 326 ns | 590 ns | 667 ns | all requests served, 0 protocol errors |
| 96 MHz | 375 / 232 ns | 375 ns | 323 ns (25 % of reads lost) | 740 ns | 11 µs (V starved) | controller saturated |

(Latency = from the edge of `PCK1B`/`PCK2B` or from the request until the data is ready.)

Reading: with this controller **at least about 133-144 MHz are needed** (speed grade
-6/-7 parts); at 96 MHz the peak traffic saturates it. The ideal model gave 10-14 % bus
usage, but assumed overlapped requests on different banks: if more margin or a lower clock
is needed, the next step is a controller with bank interleaving. As before, the real
deadline between `PCK1B` and `LOAD` remains open and cannot be derived from simulation.

The controller reads 8 bytes per request (4-beat burst on 16 bits) because sprite and fix
read exactly 8 aligned bytes; for P, M and V only the half or the byte needed is used.
Writing is one 32-bit word at a time (`dqm` masks the others): ~12 cycles per word,
comfortably above the SD loading requirements.

## How the links with the firmware are verified

`tests/test_system.py` programs the registers as `firmware/ngsd_loader.c` does (`SIZE_x`,
`ADDR_x`, then `CTRL.RUN`) and checks: SDRAM write and readback from the MCU, 240 sprite
half-rows, 150 fix reads, 174 68k reads with bank latch, 113 Z80 reads with bank switching
and 60 V reads. The SDRAM model flags tRCD/tRC/tRP/tRFC violations, missed refresh and
out-of-memory addresses; with a deliberately introduced violation (tRCD one cycle shorter)
the test fails, so the checks are active.
