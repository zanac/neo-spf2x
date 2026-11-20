/* stub.S - boot stub served by the FPGA while the game is being loaded.
 *
 * Linked at 0x000200 inside the 1 KiB boot RAM (tools/mkstub.py puts the
 * game's own 0x000-0x1FF header in front of it and patches the USER jump at
 * 0x122 to point here).  Behaviour (docs/BOOT.md):
 *   - every time the BIOS enters USER, look at the ready flag at 0x0003FE;
 *   - not ready: hand control straight back to the BIOS (SYSTEM_RETURN);
 *   - ready: copy a 20-byte trampoline to work RAM and run it from there (the
 *     FPGA is about to stop serving this code), tell the FPGA to switch to the
 *     game with a magic write, and restart the BIOS so it sees the real game.
 * Never spins, so no watchdog handling is needed in this stub.
 */
        .text
        .globl  user_entry
user_entry:
        tst.w   0x3FE.w
        beq.s   not_ready
        lea     tramp(%pc),%a0
        lea     0x100100,%a1
        moveq   #(tramp_end - tramp)/2 - 1,%d0
1:      move.w  (%a0)+,(%a1)+
        dbra    %d0,1b
        jmp     0x100100
not_ready:
        jmp     0xC00444                /* SYSTEM_RETURN */

        .even
tramp:
        move.w  #0x2700,%sr             /* interrupts off */
        move.w  #0xA5A5,0x2FFFF0        /* FPGA: stop the stub, serve the game */
        lea     0x10F300,%sp
        jmp     0xC00402                /* BIOS entry: cold start again */
tramp_end:
