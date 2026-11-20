/* ngsd_boot.c - see ngsd_boot.h */
#include "ngsd_boot.h"
#include "ngsd_stub_code.h"

#include <string.h>

int ngsd_build_boot_image(const uint8_t head[NGSD_BOOT_HEAD],
                          uint8_t out[NGSD_BOOT_BYTES])
{
    if (memcmp(head + 0x100, "NEO-GEO", 7) != 0)
        return -1;
    memset(out, 0, NGSD_BOOT_BYTES);
    memcpy(out, head, NGSD_BOOT_HEAD);
    out[0x114] = 2;                       /* eyecatcher: draw nothing        */
    out[0x122] = 0x4E; out[0x123] = 0xF9; /* JMP.L stub USER entry           */
    out[0x124] = 0x00; out[0x125] = 0x00;
    out[0x126] = (uint8_t)(NGSD_BOOT_CODE_OFF >> 8);
    out[0x127] = (uint8_t)(NGSD_BOOT_CODE_OFF & 0xFF);
    memcpy(out + NGSD_BOOT_CODE_OFF, ngsd_stub_code, NGSD_STUB_CODE_LEN);
    return 0;
}
