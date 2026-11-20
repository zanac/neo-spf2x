/* Host test of sd_spi.c against a small model of an SD card in SPI mode (v1 SDSC, v2 SDHC, no card,
 * card that never leaves idle).  The model checks the CRC7 of CMD0/CMD8 and the byte/block addressing. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../sd_spi.h"

enum { M_NONE, M_V1, M_V2, M_STUCK };
#define SECT 1024u

typedef struct {
    int mode, selected, acmd, idle, init_count, stream, ncmds;
    uint32_t next;
    uint8_t cmdbuf[6]; int ncb;
    uint8_t out[1100]; int olen, opos;
    uint32_t hz; unsigned crc_errors, bad_addr, bytes_cs_high, stream_viol;
} card_t;

static uint8_t pat(uint32_t lba, uint32_t i) { return (uint8_t)(lba * 31u + i * 7u); }

static void queue(card_t *c, const uint8_t *p, int n) { memcpy(c->out + c->olen, p, (size_t)n); c->olen += n; }
static void q1(card_t *c, uint8_t b) { queue(c, &b, 1); }

static void queue_block(card_t *c, uint32_t lba)
{
    q1(c, 0xFE);
    for (uint32_t i = 0; i < 512; i++) q1(c, pat(lba, i));
    q1(c, 0x12); q1(c, 0x34);
}

static void do_cmd(card_t *c)
{
    uint8_t *f = c->cmdbuf;
    uint8_t idx = f[0] & 0x3F;
    uint32_t arg = ((uint32_t)f[1] << 24) | ((uint32_t)f[2] << 16) | ((uint32_t)f[3] << 8) | f[4];
    int was_acmd = c->acmd; c->acmd = 0;
    c->ncmds++;
    if (c->stream && idx != 12) c->stream_viol++;     /* multi block read not stopped with CMD12 */
    c->olen = c->opos = 0;
    if (idx == 0 && f[5] != 0x95) c->crc_errors++;
    if (idx == 8 && f[5] != 0x87) c->crc_errors++;
    q1(c, 0xFF);                                     /* Ncr gap */
    switch (idx) {
    case 0: c->idle = 1; c->init_count = 0; c->stream = 0; q1(c, 0x01); break;
    case 8:
        if (c->mode == M_V1) q1(c, 0x05);
        else { q1(c, 0x01); q1(c, 0); q1(c, 0); q1(c, 0x01); q1(c, 0xAA); }
        break;
    case 55: c->acmd = 1; q1(c, c->idle ? 0x01 : 0x00); break;
    case 41:
        if (!was_acmd) { q1(c, 0x05); break; }
        if (c->mode != M_STUCK && ++c->init_count >= 3) { c->idle = 0; q1(c, 0x00); }
        else q1(c, 0x01);
        break;
    case 58: q1(c, 0x00); q1(c, c->mode == M_V2 ? 0xC0 : 0x80); q1(c, 0xFF); q1(c, 0x80); q1(c, 0x00); break;
    case 16: q1(c, arg == 512 ? 0x00 : 0x40); break;
    case 9: {
        uint8_t csd[16] = {0};
        if (c->mode == M_V2) { csd[0] = 0x40; csd[5] = 9; }            /* C_SIZE = 0 -> 1024 sectors */
        else { csd[0] = 0x00; csd[5] = 9; csd[7] = 63; csd[8] = 0xC0; }
        q1(c, 0x00); q1(c, 0xFF); q1(c, 0xFE); queue(c, csd, 16); q1(c, 0); q1(c, 0);
        break; }
    case 17: case 18: {
        uint32_t lba;
        if (c->mode == M_V2) lba = arg; else { if (arg % 512) c->bad_addr++; lba = arg / 512; }
        if (lba >= SECT) { q1(c, 0x40); break; }
        q1(c, 0x00); q1(c, 0xFF);
        queue_block(c, lba);
        if (idx == 18) { c->stream = 1; c->next = lba + 1; }
        break; }
    case 12:
        c->stream = 0; c->olen = c->opos = 0;
        q1(c, 0xFF);                                  /* stuff byte */
        q1(c, 0x00); q1(c, 0x00); q1(c, 0x00); q1(c, 0x00);   /* R1 then busy */
        break;
    default: q1(c, 0x04); break;
    }
}

static void h_cs(void *u, int level) { card_t *c = u; c->selected = !level; if (level) c->ncb = 0; }
static void h_hz(void *u, uint32_t hz) { ((card_t *)u)->hz = hz; }
static void h_delay(void *u, uint32_t ms) { (void)u; (void)ms; }
static uint8_t h_xfer(void *u, uint8_t b)
{
    card_t *c = u;
    if (c->mode == M_NONE) return 0xFF;
    if (!c->selected) { c->bytes_cs_high++; return 0xFF; }
    uint8_t r = 0xFF;
    if (c->opos < c->olen) r = c->out[c->opos++];
    else if (c->stream && c->olen) {                  /* multi block read: next block follows */
        c->olen = c->opos = 0; queue_block(c, c->next++); r = c->out[c->opos++];
    }
    if (c->ncb == 0) { if ((b & 0xC0) == 0x40) c->cmdbuf[c->ncb++] = b; }
    else { c->cmdbuf[c->ncb++] = b; if (c->ncb == 6) { c->ncb = 0; do_cmd(c); } }
    return r;
}

static int fails;
#define CHECK(x) do { if (!(x)) { printf("FAIL line %d: %s\n", __LINE__, #x); fails++; } } while (0)

static void hal(sd_hal_t *h, card_t *c)
{
    h->cs = h_cs; h->xfer = h_xfer; h->set_hz = h_hz; h->delay_ms = h_delay; h->user = c;
}

static int check_read(sd_t *sd, uint32_t lba, uint32_t n)
{
    uint8_t *buf = malloc(512u * n);
    int rc = sd_read(sd, lba, buf, n);
    int ok = (rc == SD_OK);
    for (uint32_t s = 0; ok && s < n; s++)
        for (uint32_t i = 0; i < 512; i++)
            if (buf[512u * s + i] != pat(lba + s, i)) { ok = 0; break; }
    free(buf);
    return ok;
}

int main(void)
{
    for (int mode = M_V1; mode <= M_V2; mode++) {
        card_t c; memset(&c, 0, sizeof c); c.mode = mode;
        sd_hal_t h; hal(&h, &c);
        sd_t sd;
        CHECK(sd_init(&sd, &h) == SD_OK);
        CHECK(sd.hc == (mode == M_V2));
        CHECK(sd.v2 == (mode == M_V2));
        CHECK(sd.sectors == SECT);
        CHECK(c.hz == SD_RUN_HZ);
        CHECK(c.crc_errors == 0);
        CHECK(check_read(&sd, 5, 1));
        CHECK(check_read(&sd, 0, 1));
        CHECK(check_read(&sd, 1000, 24));             /* up to the last sector */
        CHECK(check_read(&sd, 100, 7));
        CHECK(check_read(&sd, 7, 2));                 /* back to back after a multi block read */
        CHECK(check_read(&sd, 8, 1));
        uint8_t b[512];
        CHECK(sd_read(&sd, SECT, b, 1) == SD_E_ARG);
        CHECK(sd_read(&sd, 1020, b, 8) == SD_E_ARG);
        CHECK(c.bad_addr == 0);
        CHECK(c.stream_viol == 0);
        printf("card model %s: init + reads checked\n", mode == M_V2 ? "SDHC (v2)" : "SDSC (v1)");
    }
    { card_t c; memset(&c, 0, sizeof c); c.mode = M_NONE; sd_hal_t h; hal(&h, &c); sd_t sd;
      CHECK(sd_init(&sd, &h) == SD_E_NOCARD); }
    { card_t c; memset(&c, 0, sizeof c); c.mode = M_STUCK; sd_hal_t h; hal(&h, &c); sd_t sd;
      CHECK(sd_init(&sd, &h) == SD_E_INIT); }
    if (fails) { printf("test_sd: %d FAILURES\n", fails); return 1; }
    printf("test_sd: OK (SDSC/SDHC init, CRC7 of CMD0/CMD8, single and multi block reads, capacity, errors)\n");
    return 0;
}
