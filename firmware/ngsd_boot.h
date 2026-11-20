/* ngsd_boot.h - boot image the FPGA serves to the 68k while the game loads.
 * See docs/BOOT.md.  Pure data manipulation, no hardware access.           */
#ifndef NGSD_BOOT_H
#define NGSD_BOOT_H

#include <stdint.h>

enum {
    NGSD_BOOT_BYTES    = 1024,   /* boot RAM size in the FPGA               */
    NGSD_BOOT_HEAD     = 512,    /* bytes copied from the game's P region   */
    NGSD_BOOT_CODE_OFF = 0x200,  /* stub code (also the patched USER target)*/
    NGSD_BOOT_FLAG_OFF = 0x3FE   /* ready flag word, 0 = still loading      */
};

/* Builds the image from the first 512 bytes of the game's P region (68k byte
 * order).  Returns 0, or -1 if the 'NEO-GEO' signature is missing. */
int ngsd_build_boot_image(const uint8_t head[NGSD_BOOT_HEAD],
                          uint8_t out[NGSD_BOOT_BYTES]);

#endif
