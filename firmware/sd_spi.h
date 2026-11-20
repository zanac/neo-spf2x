/* sd_spi.h - SD / SDHC / SDXC card driver in SPI mode (read only).
 *
 * Wiring on the cartridge (the microSD slot sits on the RP2040, see docs/PCB.md):
 *   CLK = SCK,  CMD = MOSI,  DAT0 = MISO,  DAT3/CD = chip select (CS), DAT1/DAT2 unused.
 * (SD Physical Layer Simplified Specification, SPI mode.)  The board has 10 kOhm pull-ups on every line.
 * Hardware access goes through sd_hal_t, so the code runs on the MCU and in the host test (firmware/test).
 * A 4-bit SDIO driver (PIO) would be faster; the board is wired for it, this driver is the portable base
 * and what FatFS's disk_read() needs. */
#ifndef SD_SPI_H
#define SD_SPI_H

#include <stdint.h>

typedef struct {
    void    (*cs)(void *user, int level);          /* 1 = deselected (high), 0 = selected      */
    uint8_t (*xfer)(void *user, uint8_t out);      /* one byte full duplex                    */
    void    (*set_hz)(void *user, uint32_t hz);    /* SCK frequency; 400 kHz for init          */
    void    (*delay_ms)(void *user, uint32_t ms);
    void    *user;
} sd_hal_t;

typedef struct {
    sd_hal_t hal;
    int      hc;            /* block addressed (SDHC/SDXC) */
    int      v2;            /* card answered CMD8 (spec 2.00 or later) */
    uint32_t sectors;       /* capacity in 512-byte sectors, 0 if the CSD could not be read */
} sd_t;

enum {
    SD_OK = 0,
    SD_E_NOCARD = -1,       /* no answer to CMD0 */
    SD_E_VOLTAGE = -2,      /* CMD8 echo wrong */
    SD_E_INIT = -3,         /* ACMD41 did not finish (timeout) */
    SD_E_CMD = -4,          /* unexpected R1 */
    SD_E_TOKEN = -5,        /* data token not received */
    SD_E_ARG = -6
};

#define SD_INIT_HZ  400000u
#define SD_RUN_HZ   12500000u

int sd_init(sd_t *sd, const sd_hal_t *hal);
/* reads n sectors starting at lba into buf (n * 512 bytes) */
int sd_read(sd_t *sd, uint32_t lba, void *buf, uint32_t n);

#endif
