/* ngpk.h - NGPK (Neo Geo Pack) container parser.  Portable C99, no heap,
 * no hardware dependencies.  Format description: docs/FORMAT.md */
#ifndef NGPK_H
#define NGPK_H

#include <stddef.h>
#include <stdint.h>

#define NGPK_VERSION      1
#define NGPK_HDR_SIZE     64
#define NGPK_ENT_SIZE     32
#define NGPK_SECTOR       512
#define NGPK_MAX_REGIONS  8

/* region types (also index into the board profile and the FPGA registers) */
enum {
    NGPK_R_P  = 1,   /* 68k program                                  */
    NGPK_R_C  = 2,   /* sprite tiles, c_odd/c_even byte-interleaved   */
    NGPK_R_S  = 3,   /* fix layer tiles                               */
    NGPK_R_M  = 4,   /* Z80 program                                   */
    NGPK_R_V  = 5,   /* ADPCM samples (shared A/B)                    */
    NGPK_R_VB = 6,   /* ADPCM-B samples, only for split-ROM games     */
    NGPK_R_COUNT = 7 /* array size for tables indexed by region type  */
};

enum { NGPK_MAPPER_PLAIN = 0 };

typedef enum {
    NGPK_OK            =  0,
    NGPK_E_IO          = -1,  /* read / write callback failed              */
    NGPK_E_MAGIC       = -2,  /* not an NGPK file                          */
    NGPK_E_VERSION     = -3,  /* unsupported container version             */
    NGPK_E_HDRCRC      = -4,  /* header or region table is corrupt         */
    NGPK_E_FORMAT      = -5,  /* structurally invalid container            */
    NGPK_E_PROFILE     = -6,  /* game does not fit this cartridge board    */
    NGPK_E_REGION_CRC  = -7,  /* ROM data corrupt (bad SD read / bad file) */
    NGPK_E_MAPPER      = -8   /* mapper not supported by this firmware     */
} ngpk_err_t;

typedef struct {
    uint8_t  type;       /* NGPK_R_*                         */
    uint8_t  flags;
    uint32_t size;       /* bytes of real ROM data           */
    uint32_t file_off;   /* byte offset in the file (sector aligned) */
    uint32_t crc32;      /* CRC-32 (zlib) of the region data */
} ngpk_region_t;

typedef struct {
    uint16_t version;
    uint32_t flags;
    uint16_t mapper;
    uint16_t mapper_arg;
    uint16_t ngh;                      /* NGH number, 0 for homebrew */
    char     title[33];                /* NUL terminated             */
    uint32_t nregions;
    ngpk_region_t region[NGPK_MAX_REGIONS];
} ngpk_info_t;

/* Reads 'len' bytes at absolute file offset 'offset'. Returns 0 on success. */
typedef int (*ngpk_read_fn)(void *user, uint32_t offset, void *dst,
                            uint32_t len);

/* zlib compatible CRC-32; start with crc = 0 and chain calls. */
uint32_t ngpk_crc32(uint32_t crc, const void *data, size_t len);

/* Parses and validates header + region table. Returns NGPK_OK or an error. */
int ngpk_parse(ngpk_read_fn rd, void *user, ngpk_info_t *out);

/* Region lookup by type, NULL when the game has no such region. */
const ngpk_region_t *ngpk_find(const ngpk_info_t *info, unsigned type);

const char *ngpk_strerror(int err);

#endif
