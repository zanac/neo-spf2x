/* ngpk.c - NGPK container parser (see ngpk.h) */
#include "ngpk.h"

#include <string.h>

static uint32_t crc_table[256];
static int crc_ready;

static void crc_init(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++)
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        crc_table[i] = c;
    }
    crc_ready = 1;
}

uint32_t ngpk_crc32(uint32_t crc, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    if (!crc_ready)
        crc_init();
    crc = ~crc;
    while (len--)
        crc = crc_table[(crc ^ *p++) & 0xFFu] ^ (crc >> 8);
    return ~crc;
}

static uint16_t le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static uint32_t align_up(uint32_t v)
{
    return (v + NGPK_SECTOR - 1u) & ~(uint32_t)(NGPK_SECTOR - 1u);
}

int ngpk_parse(ngpk_read_fn rd, void *user, ngpk_info_t *out)
{
    uint8_t hdr[NGPK_HDR_SIZE];
    uint8_t tab[NGPK_MAX_REGIONS * NGPK_ENT_SIZE];
    uint8_t tmp[NGPK_HDR_SIZE];
    uint32_t n, crc;

    if (rd(user, 0, hdr, NGPK_HDR_SIZE))
        return NGPK_E_IO;
    if (memcmp(hdr, "NGPK", 4) != 0)
        return NGPK_E_MAGIC;
    if (le16(hdr + 4) != NGPK_VERSION || le16(hdr + 6) != NGPK_HDR_SIZE)
        return NGPK_E_VERSION;

    n = le32(hdr + 12);
    if (n == 0 || n > NGPK_MAX_REGIONS)
        return NGPK_E_FORMAT;
    if (rd(user, NGPK_HDR_SIZE, tab, n * NGPK_ENT_SIZE))
        return NGPK_E_IO;

    /* header CRC covers the header (CRC field zeroed) and the region table */
    memcpy(tmp, hdr, NGPK_HDR_SIZE);
    memset(tmp + 56, 0, 4);
    crc = ngpk_crc32(0, tmp, NGPK_HDR_SIZE);
    crc = ngpk_crc32(crc, tab, n * NGPK_ENT_SIZE);
    if (crc != le32(hdr + 56))
        return NGPK_E_HDRCRC;

    memset(out, 0, sizeof *out);
    out->version    = le16(hdr + 4);
    out->flags      = le32(hdr + 8);
    out->nregions   = n;
    out->mapper     = le16(hdr + 16);
    out->mapper_arg = le16(hdr + 18);
    out->ngh        = le16(hdr + 20);
    memcpy(out->title, hdr + 24, 32);
    out->title[32] = '\0';

    uint32_t data_start = align_up(NGPK_HDR_SIZE + n * NGPK_ENT_SIZE);
    for (uint32_t i = 0; i < n; i++) {
        const uint8_t *e = tab + i * NGPK_ENT_SIZE;
        ngpk_region_t *r = &out->region[i];
        r->type     = e[0];
        r->flags    = e[1];
        r->size     = le32(e + 4);
        r->file_off = le32(e + 8);
        r->crc32    = le32(e + 12);

        if (r->type < NGPK_R_P || r->type > NGPK_R_VB)
            return NGPK_E_FORMAT;
        if (r->size == 0 || r->file_off % NGPK_SECTOR ||
            r->file_off < data_start ||
            r->size > 0xFFFFFFFFu - NGPK_SECTOR - r->file_off)
            return NGPK_E_FORMAT;
        for (uint32_t j = 0; j < i; j++) {
            const ngpk_region_t *o = &out->region[j];
            if (o->type == r->type)
                return NGPK_E_FORMAT;
            if (r->file_off < o->file_off + align_up(o->size) &&
                o->file_off < r->file_off + align_up(r->size))
                return NGPK_E_FORMAT;
        }
    }
    return NGPK_OK;
}

const ngpk_region_t *ngpk_find(const ngpk_info_t *info, unsigned type)
{
    for (uint32_t i = 0; i < info->nregions; i++)
        if (info->region[i].type == type)
            return &info->region[i];
    return NULL;
}

const char *ngpk_strerror(int err)
{
    switch (err) {
    case NGPK_OK:           return "ok";
    case NGPK_E_IO:         return "I/O error";
    case NGPK_E_MAGIC:      return "not an NGPK file";
    case NGPK_E_VERSION:    return "unsupported NGPK version";
    case NGPK_E_HDRCRC:     return "header CRC mismatch";
    case NGPK_E_FORMAT:     return "invalid container";
    case NGPK_E_PROFILE:    return "game does not fit this board";
    case NGPK_E_REGION_CRC: return "ROM data CRC mismatch";
    case NGPK_E_MAPPER:     return "mapper not supported";
    default:                return "unknown error";
    }
}
