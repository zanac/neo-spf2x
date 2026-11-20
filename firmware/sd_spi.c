#include "sd_spi.h"

#include <string.h>

enum { CMD0 = 0, CMD8 = 8, CMD9 = 9, CMD12 = 12, CMD16 = 16, CMD17 = 17, CMD18 = 18,
       CMD55 = 55, CMD58 = 58, ACMD41 = 41 };
#define R1_IDLE   0x01u
#define R1_ILLEGAL 0x04u
#define TOKEN_START 0xFEu

/* CRC7, polynomial x^7 + x^3 + 1; the command frame carries (crc << 1) | 1 */
static uint8_t crc7(const uint8_t *p, int n)
{
    uint8_t crc = 0;
    for (int i = 0; i < n; i++) {
        uint8_t d = p[i];
        for (int j = 0; j < 8; j++) {
            crc <<= 1;
            if ((d ^ crc) & 0x80) crc ^= 0x09;
            d <<= 1;
        }
    }
    return crc & 0x7F;
}

static void deselect(sd_t *sd)
{
    sd->hal.cs(sd->hal.user, 1);
    sd->hal.xfer(sd->hal.user, 0xFF);        /* 8 extra clocks release DO */
}

static int wait_ready(sd_t *sd)
{
    for (int i = 0; i < 100000; i++)
        if (sd->hal.xfer(sd->hal.user, 0xFF) == 0xFF) return 0;
    return -1;
}

/* sends a command with the card selected; returns R1 (0xFF = no answer) */
static uint8_t cmd_raw(sd_t *sd, uint8_t c, uint32_t arg, int wait, int stuff)
{
    uint8_t f[6] = { (uint8_t)(0x40 | c), (uint8_t)(arg >> 24), (uint8_t)(arg >> 16), (uint8_t)(arg >> 8),
                     (uint8_t)arg, 0 };
    f[5] = (uint8_t)((crc7(f, 5) << 1) | 1);
    sd->hal.cs(sd->hal.user, 0);
    if (wait && wait_ready(sd)) return 0xFF;
    for (int i = 0; i < 6; i++) sd->hal.xfer(sd->hal.user, f[i]);
    if (stuff) sd->hal.xfer(sd->hal.user, 0xFF);           /* CMD12: first byte after it is stuff */
    uint8_t r = 0xFF;
    for (int i = 0; i < 10 && (r & 0x80); i++) r = sd->hal.xfer(sd->hal.user, 0xFF);
    return r;
}

static uint8_t cmd(sd_t *sd, uint8_t c, uint32_t arg)
{
    return cmd_raw(sd, c, arg, c != CMD0, 0);
}

static int rcv_block(sd_t *sd, uint8_t *dst, int len)
{
    uint8_t t = 0xFF;
    for (int i = 0; i < 100000 && t == 0xFF; i++) t = sd->hal.xfer(sd->hal.user, 0xFF);
    if (t != TOKEN_START) return SD_E_TOKEN;
    for (int i = 0; i < len; i++) dst[i] = sd->hal.xfer(sd->hal.user, 0xFF);
    sd->hal.xfer(sd->hal.user, 0xFF);        /* CRC, not checked (CRC is off in SPI mode) */
    sd->hal.xfer(sd->hal.user, 0xFF);
    return SD_OK;
}

int sd_init(sd_t *sd, const sd_hal_t *hal)
{
    memset(sd, 0, sizeof *sd);
    sd->hal = *hal;
    sd->hal.set_hz(sd->hal.user, SD_INIT_HZ);
    sd->hal.cs(sd->hal.user, 1);
    for (int i = 0; i < 10; i++) sd->hal.xfer(sd->hal.user, 0xFF);   /* >= 74 clocks with CS high */

    uint8_t r = 0xFF;
    for (int i = 0; i < 10; i++) {
        r = cmd(sd, CMD0, 0);
        deselect(sd);
        if (r == R1_IDLE) break;
        sd->hal.delay_ms(sd->hal.user, 1);
    }
    if (r != R1_IDLE) return SD_E_NOCARD;

    r = cmd(sd, CMD8, 0x1AA);
    if (r & R1_ILLEGAL) {                                   /* version 1 card */
        deselect(sd);
    } else {
        uint8_t ocr[4];
        for (int i = 0; i < 4; i++) ocr[i] = sd->hal.xfer(sd->hal.user, 0xFF);
        deselect(sd);
        if (r != R1_IDLE) return SD_E_CMD;
        if ((ocr[2] & 0x0F) != 0x01 || ocr[3] != 0xAA) return SD_E_VOLTAGE;
        sd->v2 = 1;
    }

    int done = 0;
    for (int i = 0; i < 1000 && !done; i++) {               /* up to ~1 s */
        r = cmd(sd, CMD55, 0);
        deselect(sd);
        if (r > R1_IDLE) return SD_E_CMD;
        r = cmd(sd, ACMD41, sd->v2 ? 0x40000000u : 0);
        deselect(sd);
        if (r == 0) done = 1;
        else if (r != R1_IDLE) return SD_E_CMD;
        else sd->hal.delay_ms(sd->hal.user, 1);
    }
    if (!done) return SD_E_INIT;

    if (sd->v2) {
        r = cmd(sd, CMD58, 0);
        uint8_t ocr[4];
        for (int i = 0; i < 4; i++) ocr[i] = sd->hal.xfer(sd->hal.user, 0xFF);
        deselect(sd);
        if (r != 0) return SD_E_CMD;
        sd->hc = (ocr[0] & 0x40) != 0;                       /* CCS */
    }
    if (!sd->hc) {
        r = cmd(sd, CMD16, 512);
        deselect(sd);
        if (r != 0) return SD_E_CMD;
    }

    uint8_t csd[16];
    r = cmd(sd, CMD9, 0);
    if (r == 0 && rcv_block(sd, csd, 16) == SD_OK) {
        if ((csd[0] >> 6) == 1) {                            /* CSD v2: (C_SIZE + 1) * 1024 sectors */
            uint32_t cs = ((uint32_t)(csd[7] & 0x3F) << 16) | ((uint32_t)csd[8] << 8) | csd[9];
            sd->sectors = (cs + 1) << 10;
        } else {                                             /* CSD v1 */
            uint32_t cs = ((uint32_t)(csd[6] & 3) << 10) | ((uint32_t)csd[7] << 2) | (csd[8] >> 6);
            uint32_t mult = ((csd[9] & 3) << 1) | (csd[10] >> 7);
            uint32_t bl = csd[5] & 15;
            sd->sectors = (uint32_t)(((uint64_t)(cs + 1) << (mult + 2)) << bl >> 9);
        }
    }
    deselect(sd);
    sd->hal.set_hz(sd->hal.user, SD_RUN_HZ);
    return SD_OK;
}

int sd_read(sd_t *sd, uint32_t lba, void *buf, uint32_t n)
{
    uint8_t *p = (uint8_t *)buf;
    if (n == 0) return SD_OK;
    if (sd->sectors && (lba >= sd->sectors || n > sd->sectors - lba)) return SD_E_ARG;
    uint32_t arg = sd->hc ? lba : lba * 512u;
    uint8_t r = cmd(sd, n == 1 ? CMD17 : CMD18, arg);
    if (r != 0) { deselect(sd); return SD_E_CMD; }
    int rc = SD_OK;
    for (uint32_t i = 0; i < n && rc == SD_OK; i++) rc = rcv_block(sd, p + 512u * i, 512);
    if (n > 1) {
        cmd_raw(sd, CMD12, 0, 0, 1);                         /* R1b: the busy that follows is awaited by the next cmd() */
    }
    deselect(sd);
    return rc;
}
