/* ngsd_loader.c - see ngsd_loader.h */
#include "ngsd_loader.h"

#define MiB (1024u * 1024u)

const ngsd_profile_t NGSD_PROFILE_64M = {
    .name = "ngsd-64M",
    .sdram_bytes = 64u * MiB,
    .slot = {
        [NGPK_R_P]  = { .base = 0x0000000u, .cap =  8u * MiB },
        [NGPK_R_V]  = { .base = 0x0800000u, .cap = 16u * MiB },
        [NGPK_R_S]  = { .base = 0x1800000u, .cap =  1u * MiB, .layout = 1 },
        [NGPK_R_M]  = { .base = 0x1900000u, .cap =  1u * MiB },
        [NGPK_R_C]  = { .base = 0x1A00000u, .cap = 38u * MiB, .layout = 1 },
        /* NGPK_R_VB: no slot, games with split ADPCM-A/B ROMs are refused */
    },
};

static int check_profile(const ngpk_info_t *info, const ngsd_profile_t *prof)
{
    if (!ngpk_find(info, NGPK_R_P) || !ngpk_find(info, NGPK_R_C))
        return NGPK_E_FORMAT;
    for (uint32_t i = 0; i < info->nregions; i++) {
        const ngpk_region_t *r = &info->region[i];
        const ngsd_slot_t *s = &prof->slot[r->type];
        if (s->cap == 0 || r->size > s->cap)
            return NGPK_E_PROFILE;
        if (s->base > prof->sdram_bytes ||
            s->cap > prof->sdram_bytes - s->base)
            return NGPK_E_PROFILE;
        if ((r->flags & 0x0Fu) != s->layout)
            return NGPK_E_LAYOUT;
    }
    return NGPK_OK;
}

static int load_region(const ngsd_hal_t *hal, const ngsd_slot_t *slot,
                       const ngpk_region_t *r, uint8_t *buf, uint32_t buf_len,
                       uint32_t *done_total, uint32_t grand_total)
{
    uint32_t pos = 0, crc = 0;

    while (pos < r->size) {
        uint32_t n = r->size - pos;
        if (n > buf_len)
            n = buf_len;
        if (hal->read(hal->user, r->file_off + pos, buf, n))
            return NGPK_E_IO;
        crc = ngpk_crc32(crc, buf, n);
        if (hal->sdram_write(hal->user, slot->base + pos, buf, n))
            return NGPK_E_IO;
        pos += n;
        *done_total += n;
        if (hal->progress)
            hal->progress(hal->user, *done_total, grand_total);
    }
    return crc == r->crc32 ? NGPK_OK : NGPK_E_REGION_CRC;
}

int ngsd_load(const ngsd_hal_t *hal, const ngsd_profile_t *profile,
              ngpk_info_t *info, void *buf, uint32_t buf_len)
{
    int err;
    uint32_t total = 0, done = 0;

    if (!buf || buf_len == 0)
        return NGPK_E_FORMAT;

    err = ngpk_parse(hal->read, hal->user, info);
    if (err)
        return err;
    if (info->mapper != NGPK_MAPPER_PLAIN)
        return NGPK_E_MAPPER;
    err = check_profile(info, profile);
    if (err)
        return err;

    /* hold the cartridge idle while SDRAM is being filled */
    if (hal->fpga_reg(hal->user, NGSD_REG_CTRL, 0))
        return NGPK_E_IO;

    for (uint32_t i = 0; i < info->nregions; i++)
        total += info->region[i].size;

    for (uint32_t i = 0; i < info->nregions; i++) {
        const ngpk_region_t *r = &info->region[i];
        err = load_region(hal, &profile->slot[r->type], r, (uint8_t *)buf,
                          buf_len, &done, total);
        if (err)
            return err;
    }

    /* data is in and verified: describe the layout, then release */
    if (hal->fpga_reg(hal->user, NGSD_REG_MAPPER, info->mapper) ||
        hal->fpga_reg(hal->user, NGSD_REG_MAPPER_ARG, info->mapper_arg))
        return NGPK_E_IO;
    for (unsigned t = NGPK_R_P; t <= NGPK_R_VB; t++) {
        const ngpk_region_t *r = ngpk_find(info, t);
        if (hal->fpga_reg(hal->user, NGSD_REG_SIZE_BASE + (t - 1),
                          r ? r->size : 0) ||
            hal->fpga_reg(hal->user, NGSD_REG_ADDR_BASE + (t - 1),
                          profile->slot[t].base))
            return NGPK_E_IO;
    }
    if (hal->fpga_reg(hal->user, NGSD_REG_CTRL, NGSD_CTRL_RUN))
        return NGPK_E_IO;
    return NGPK_OK;
}
