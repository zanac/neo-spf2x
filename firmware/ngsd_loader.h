/* ngsd_loader.h - streams an NGPK game from SD into the cartridge SDRAM and
 * configures the FPGA.  Hardware access goes through ngsd_hal_t, so the same
 * code runs on the MCU and in the host test (firmware/test).            */
#ifndef NGSD_LOADER_H
#define NGSD_LOADER_H

#include "ngpk.h"

/* ---- FPGA register map (contract with the gateware, see docs) ---------- */
enum {
    NGSD_REG_CTRL       = 0x00,
    NGSD_REG_MAPPER     = 0x01,
    NGSD_REG_MAPPER_ARG = 0x02,
    NGSD_REG_SIZE_BASE  = 0x10,  /* + (region type - 1): bytes in that region */
    NGSD_REG_ADDR_BASE  = 0x20   /* + (region type - 1): SDRAM base address   */
};
enum {
    NGSD_CTRL_RUN = 1u << 0      /* 0: cartridge held idle, 1: game running */
};

/* ---- board profile: where each region lives in SDRAM -------------------- */
typedef struct {
    uint32_t base;               /* SDRAM byte address of the region */
    uint32_t cap;                /* maximum size in bytes, 0 = region unsupported */
    uint8_t  layout;             /* layout id the gateware expects (low nibble
                                    of the region flags): 0 canonical, 1 sdram1 */
} ngsd_slot_t;

typedef struct {
    const char *name;
    uint32_t    sdram_bytes;
    ngsd_slot_t slot[NGPK_R_COUNT];   /* indexed by NGPK_R_*, [0] unused */
} ngsd_profile_t;

/* 64 MiB of SDRAM; P 8, V 16, S 1, M 1, C 38 MiB.  Design choice of this
 * project, not a hardware requirement: change it together with the gateware. */
extern const ngsd_profile_t NGSD_PROFILE_64M;

/* ---- hardware abstraction ---------------------------------------------- */
typedef struct {
    ngpk_read_fn read;                                  /* from the .ngpk file */
    int  (*sdram_write)(void *user, uint32_t addr, const void *src,
                        uint32_t len);                  /* 0 = ok              */
    int  (*fpga_reg)(void *user, uint32_t reg, uint32_t value);   /* 0 = ok    */
    void (*progress)(void *user, uint32_t done, uint32_t total);  /* optional  */
    void *user;
} ngsd_hal_t;

/* Loads the game.  'buf' is a caller supplied transfer buffer (any length
 * >= 1; 4-32 KiB is typical).  On success the FPGA has been configured and
 * released (CTRL.RUN set).  On any error RUN is never set.  'info' is
 * filled as soon as the header parsed, even if loading fails later. */
int ngsd_load(const ngsd_hal_t *hal, const ngsd_profile_t *profile,
              ngpk_info_t *info, void *buf, uint32_t buf_len);

#endif
