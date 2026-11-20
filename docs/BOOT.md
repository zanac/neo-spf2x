# Boot: how the console sees the cartridge while the SD card loads

The problem: the BIOS reads the cartridge right at power-on, but copying tens of MiB
from the microSD to the SDRAM takes seconds. This document separates what is
documented from what is inferred, and describes the chosen solution (implemented
and simulated, **not proven on a console**).

## 1. What is known

**Wait signals (PROG).** `ROMWAIT`, `PWAIT0/1` and `PDTACK` are pins the cartridge
can drive towards the console. From the NeoGeo_MiSTer core's model
(`rtl/io/c1_wait.v`, read to understand the behaviour, not copied):

* `ROMWAIT` active (low) adds a **fixed number** of wait states to accesses to the
  68k's ROM area; `PWAIT0/1` do the same (1 or 2 states, depending on the
  combination) for the port area. The wait is counted by the console's chip: there
  is no wait of arbitrary duration.
* `PDTACK` in the model is commented out, with the warning that if held to ground it
  "might hang the CPU": the core keeps it inactive. Its real function is neither
  documented nor verified.
* In other words: **these pins are not for holding the console still for seconds**.
  They are for adding a fixed wait state when the ROM is slow, which is what we need
  for the P served by the SDRAM (the MiSTer core inserts a wait state too).

**Header and BIOS** (neogeodev wiki, *68k program header* page): the BIOS recognizes
the cartridge by the `NEO-GEO` string at `$100` and by a second code (pointer at
`$182`, the "security code"). `$114` says whether the logo is drawn by the BIOS (0),
the game (1) or nobody (2). `$122` is a `JMP` to the USER subroutine, which the BIOS
**reaches with a jump** and reads the request in `BIOS_USER_REQUEST` (`$10FDAE`: 0
init, 1 logo, 2 demo, 3 title). The USER must end with a jump to `SYSTEM_RETURN`
(`$C00444`); during request 0 interrupts are disabled. BIOS entry point: `$C00402`.

**Precedent.** A commercial AES cartridge with microSD exists (NeoSD, by Stone Age
Gamer). From its manual: at first start the console boots into a menu shown by the
cartridge; choosing a game loads it into the internal memory and the console
**restarts** into the game; if the header is not recognized by the BIOS the console
shows a crosshatch screen. I do not know its internals, but it confirms that the
"the cartridge serves its own program, then restarts the console onto the game"
approach works on AES.

## 2. Choice: boot stub served by the FPGA

1. **Power-on.** The FPGA serves the 68k a 1 KiB boot image from internal RAM
   (`ng_boot.v`): at first the default image written in the configuration, then the
   one built by the MCU.
2. **The image** (`tools/mkstub.py`, `firmware/ngsd_boot.c`) is the game's own header
   (first 512 bytes of the P: vectors, `NEO-GEO`, security code), with `$114 = 2` (no
   logo) and the `JMP` at `$122` pointed to the stub at `$200`, plus the program
   `boot/stub.S` (60 bytes) and a "ready" flag at `$3FE`. The security code is not in
   the repo: it comes from the user's game.
3. **The stub** (on every USER entry): if the flag is 0 it jumps to `SYSTEM_RETURN`
   doing nothing else; if it is 1 it copies a 24-byte routine into work RAM
   (`$100100`), runs it, writes the magic word `$A5A5` at `$2FFFF0`, sets the stack
   and jumps to `$C00402`: the BIOS restarts and this time finds the game.
4. **MCU** (`ngsd_load`): sets `CTRL.STUB`, writes the image into the boot RAM, copies
   the regions into SDRAM with the CRCs, programs `SIZE_x`/`ADDR_x`, sets
   `CTRL.RUN|STUB` and writes the flag. If anything fails the flag stays 0 and `RUN`
   is never set: the console stays in the stub (today without an error message).
5. **FPGA** (`ng_pbank.v`): in stub mode, reads of P1 below 1 KiB come from the boot
   RAM; the rest, and the whole bank window, from the SDRAM. The `$A5A5` write at
   `$2FFFF0` clears `STUB` **without touching the bank latch** (verified in
   simulation) and from then on the whole P comes from the SDRAM.

An alternative without a stub exists (leave the console waiting on a pin): discarded
for what was said above about the wait pins.

## 3. What has been verified

* The program assembles (m68k binutils) and the disassembly matches the scheme above;
  the C firmware and `mkstub.py` produce the same image (checked by the loader test).
* Simulation of the whole path: image served from the boot RAM, flag 0 → 1, reads
  above 1 KiB from the SDRAM during stub mode, magic write, switch to the game, bank
  latch preserved (`test_system.py`).
* The loader checks that on an error (profile, CRC, layout) the flag is never written
  and `RUN` is never set.

## 4. What is NOT verified (to try on hardware or in an emulator)

* That the AES BIOS calls USER continuously while the flag is 0, and that closing
  every call with `SYSTEM_RETURN` does not trip the watchdog.
* That the restart with `jmp $C00402` from inside USER (stack reset to `$10F300`, RAM
  `$100100` used as trampoline) is equivalent to a cold start: state of the LSPC, Z80,
  backup RAM, system registers. The alternative is to really drive `RESET` (PROG pin
  33, direction not verified) or a 68k `reset`.
* How much time passes from power-on to the first header check: if it is shorter than
  the FPGA start-up (configuration) the console might see the cartridge as absent.
  `BOOT_HEX` preloads the default image in the configuration but this must be
  measured.
* That games with `$114` other than 2 and NGH `0` (used by homebrew: `spf2ng` has
  `0x0539`) are accepted by the BIOS: the wiki says `0000` is forbidden.
* A permanent `ROMWAIT` (1 wait state) to cover the SDRAM latency on P reads: the
  real margin has to be measured.
* **MVS:** the BIOS and boot flow are different (see `docs/MVS.md`); this stub was
  designed for the AES.

## 5. How to try it without a cartridge

`python3 tools/mkstub.py game.p1 --swap16 -o boot.bin --ready` produces the image with
the flag at 1. Its effect on a real console or in an emulator is only visible if the P
is served from that image; in an emulator like Geolith (with a legitimate BIOS) a 1 MiB
P1 containing that image at the top can be loaded: it should boot, go through the
stub and restart in a loop, which would prove the path BIOS → USER → trampoline →
restart up to the magic write (which has no effect in an emulator).
