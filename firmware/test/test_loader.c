/* Host test for the loader: a .ngpk file plays the SD card, a malloc'ed
 * buffer plays the SDRAM and a register array plays the FPGA.
 *
 *   test_loader game.ngpk unpacked_dir
 *
 * 'unpacked_dir' holds P.bin, C.bin... as written by `ngpk.py unpack`.      */
#include "../ngsd_loader.h"
#include "../ngsd_boot.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    FILE    *f;
    uint8_t *sdram;
    uint32_t sdram_size;
    uint32_t writes;
    uint32_t regs[256];
    int      ctrl_writes;
    int      run_written;
    int      held_before_first_write;
    uint32_t last_progress;
    uint16_t boot[NGSD_BOOT_BYTES / 2];
    uint32_t boot_idx;
    int      boot_writes;
    int      stub_before_data;     /* CTRL.STUB was set before the first boot word */
} mock_t;

static int failures;
#define CHECK(cond, ...)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            printf("  FAIL %s:%d: ", __FILE__, __LINE__);                     \
            printf(__VA_ARGS__);                                              \
            printf("\n");                                                     \
            failures++;                                                       \
        }                                                                     \
    } while (0)

static int m_read(void *u, uint32_t off, void *dst, uint32_t len)
{
    mock_t *m = u;
    if (fseek(m->f, (long)off, SEEK_SET))
        return -1;
    return fread(dst, 1, len, m->f) == len ? 0 : -1;
}

static int m_write(void *u, uint32_t addr, const void *src, uint32_t len)
{
    mock_t *m = u;
    if ((uint64_t)addr + len > m->sdram_size)
        return -1;
    if (m->writes == 0)
        m->held_before_first_write = (m->ctrl_writes > 0 &&
                                      (m->regs[0] & NGSD_CTRL_RUN) == 0);
    memcpy(m->sdram + addr, src, len);
    m->writes++;
    return 0;
}

static int m_reg(void *u, uint32_t reg, uint32_t val)
{
    mock_t *m = u;
    if (reg > 255)
        return -1;
    m->regs[reg] = val;
    if (reg == NGSD_REG_BOOT_ADDR)
        m->boot_idx = val;
    if (reg == NGSD_REG_BOOT_DATA) {
        if (m->boot_idx >= NGSD_BOOT_BYTES / 2)
            return -1;
        if (m->boot_writes == 0)
            m->stub_before_data = (m->regs[NGSD_REG_CTRL] & NGSD_CTRL_STUB) != 0;
        m->boot_writes++;
        m->boot[m->boot_idx++] = (uint16_t)val;
    }
    if (reg == NGSD_REG_CTRL) {
        m->ctrl_writes++;
        if (val & NGSD_CTRL_RUN)
            m->run_written = 1;
    }
    return 0;
}

static void m_progress(void *u, uint32_t done, uint32_t total)
{
    mock_t *m = u;
    (void)total;
    m->last_progress = done;
}

static uint8_t *slurp(const char *path, uint32_t *len)
{
    FILE *f = fopen(path, "rb");
    uint8_t *b;
    long n;
    if (!f) {
        printf("cannot open %s\n", path);
        exit(2);
    }
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    b = malloc((size_t)n ? (size_t)n : 1);
    if (fread(b, 1, (size_t)n, f) != (size_t)n)
        exit(2);
    fclose(f);
    *len = (uint32_t)n;
    return b;
}

static int run(const char *pack, const ngsd_profile_t *prof, uint32_t bufsz,
               mock_t *m, ngpk_info_t *info)
{
    ngsd_hal_t hal = { m_read, m_write, m_reg, m_progress, m };
    uint8_t *buf = malloc(bufsz);
    int err;

    memset(m, 0, sizeof *m);
    m->f = fopen(pack, "rb");
    if (!m->f) {
        printf("cannot open %s\n", pack);
        exit(2);
    }
    m->sdram_size = prof->sdram_bytes;
    m->sdram = calloc(m->sdram_size, 1);
    err = ngsd_load(&hal, prof, info, buf, bufsz);
    fclose(m->f);
    free(buf);
    return err;
}

static void free_mock(mock_t *m)
{
    free(m->sdram);
    m->sdram = NULL;
}

static const char *const NAMES[NGPK_R_COUNT] = { "?", "P", "C", "S", "M",
                                                  "V", "VB" };

int main(int argc, char **argv)
{
    if (argc < 3 || argc > 5) {
        printf("usage: %s game.ngpk unpacked_dir [canonical.ngpk [expected_boot.bin]]\n", argv[0]);
        return 2;
    }
    const char *pack = argv[1], *dir = argv[2];
    const ngsd_profile_t *prof = &NGSD_PROFILE_64M;
    static const uint32_t sizes[] = { 512, 1000, 4096, 65536 };
    mock_t m;
    ngpk_info_t info;
    int err;

    CHECK(ngsd_profile_check(&NGSD_PROFILE_64M) == 0, "64M profile layout");
    CHECK(ngsd_profile_check(&NGSD_PROFILE_128M) == 0, "128M profile layout");
    {   /* the same game loads with the 128M profile as long as it has the sdram1 layout */
        err = run(pack, &NGSD_PROFILE_128M, 4096, &m, &info);
        CHECK(err == NGPK_OK, "load with ngsd-128M: %s", ngpk_strerror(err));
        free_mock(&m);
    }

    /* 1. good load with several transfer buffer sizes -------------------- */
    for (unsigned s = 0; s < sizeof sizes / sizeof *sizes; s++) {
        printf("load, buffer %u bytes\n", sizes[s]);
        err = run(pack, prof, sizes[s], &m, &info);
        CHECK(err == NGPK_OK, "ngsd_load: %s", ngpk_strerror(err));
        CHECK(m.run_written, "RUN not set after a good load");
        CHECK(m.held_before_first_write, "cartridge not held before SDRAM writes");
        CHECK(m.regs[NGSD_REG_CTRL] == (NGSD_CTRL_RUN | NGSD_CTRL_STUB),
              "final CTRL wrong");
        CHECK(m.stub_before_data, "stub not enabled before boot RAM was written");
        CHECK(m.boot_writes == NGSD_BOOT_BYTES / 2 + 1, "boot RAM writes: %d",
              m.boot_writes);
        CHECK(m.boot[NGSD_BOOT_FLAG_OFF / 2] == 1, "ready flag not set");
        {   /* the boot image itself */
            uint8_t head[NGSD_BOOT_HEAD], want[NGSD_BOOT_BYTES];
            uint32_t flen;
            char path[1024];
            snprintf(path, sizeof path, "%s/P.bin", dir);
            uint8_t *pp = slurp(path, &flen);
            memcpy(head, pp, NGSD_BOOT_HEAD);
            free(pp);
            CHECK(ngsd_build_boot_image(head, want) == 0, "boot image build");
            for (unsigned i = 0; i < NGSD_BOOT_BYTES; i += 2) {
                uint16_t w = (uint16_t)((want[i] << 8) | want[i + 1]);
                if (i == NGSD_BOOT_FLAG_OFF)
                    w = 1;
                if (m.boot[i / 2] != w) {
                    CHECK(0, "boot RAM word %u: %04x vs %04x", i / 2,
                          m.boot[i / 2], w);
                    break;
                }
            }
            if (argc == 5) {            /* image built by tools/mkstub.py */
                uint32_t blen;
                uint8_t *ex = slurp(argv[4], &blen);
                CHECK(blen == NGSD_BOOT_BYTES, "expected boot image size");
                for (unsigned i = 0; blen == NGSD_BOOT_BYTES && i < blen; i += 2) {
                    uint16_t w = (uint16_t)((ex[i] << 8) | ex[i + 1]);
                    if (i == NGSD_BOOT_FLAG_OFF)
                        w = 1;
                    if (m.boot[i / 2] != w) {
                        CHECK(0, "differs from mkstub.py at word %u", i / 2);
                        break;
                    }
                }
                free(ex);
            }
        }

        uint32_t total = 0;
        for (uint32_t i = 0; err == NGPK_OK && i < info.nregions; i++) {
            const ngpk_region_t *r = &info.region[i];
            char path[1024];
            uint32_t flen;
            snprintf(path, sizeof path, "%s/%s.bin", dir, NAMES[r->type]);
            uint8_t *ref = slurp(path, &flen);
            const ngsd_slot_t *sl = &prof->slot[r->type];
            CHECK(flen == r->size, "%s: size %u vs %u", NAMES[r->type], flen,
                  r->size);
            CHECK(memcmp(m.sdram + sl->base, ref, flen) == 0,
                  "%s region differs in SDRAM", NAMES[r->type]);
            /* nothing written past the end of the region */
            uint32_t tail = sl->cap - r->size;
            if (tail > 4096)
                tail = 4096;
            for (uint32_t k = 0; k < tail; k++)
                if (m.sdram[sl->base + r->size + k]) {
                    CHECK(0, "%s: stray byte after region", NAMES[r->type]);
                    break;
                }
            CHECK(m.regs[NGSD_REG_SIZE_BASE + r->type - 1] == r->size,
                  "SIZE reg %s", NAMES[r->type]);
            CHECK(m.regs[NGSD_REG_ADDR_BASE + r->type - 1] == sl->base,
                  "ADDR reg %s", NAMES[r->type]);
            total += r->size;
            free(ref);
        }
        CHECK(m.last_progress == total, "progress ended at %u of %u",
              m.last_progress, total);
        free_mock(&m);
    }

    /* 2. flipped bit inside the C data must be caught, RUN never set ----- */
    {
        printf("corrupt ROM data\n");
        uint32_t len;
        uint8_t *img = slurp(pack, &len);
        ngpk_info_t tmp;
        mock_t t = { .f = fopen(pack, "rb") };
        CHECK(ngpk_parse(m_read, &t, &tmp) == NGPK_OK, "parse");
        fclose(t.f);
        const ngpk_region_t *c = ngpk_find(&tmp, NGPK_R_C);
        img[c->file_off + c->size / 2] ^= 0x10;
        const char *bad = "bad_data.ngpk";
        FILE *o = fopen(bad, "wb");
        fwrite(img, 1, len, o);
        fclose(o);
        free(img);
        err = run(bad, prof, 4096, &m, &info);
        CHECK(err == NGPK_E_REGION_CRC, "got %s", ngpk_strerror(err));
        CHECK(!m.run_written, "RUN set despite bad CRC");
        free_mock(&m);
        remove(bad);
    }

    /* 3. corrupt header ---------------------------------------------------- */
    {
        printf("corrupt header\n");
        uint32_t len;
        uint8_t *img = slurp(pack, &len);
        img[16] ^= 1; /* mapper field */
        const char *bad = "bad_hdr.ngpk";
        FILE *o = fopen(bad, "wb");
        fwrite(img, 1, len < 4096 ? len : 4096, o);
        fclose(o);
        free(img);
        err = run(bad, prof, 4096, &m, &info);
        CHECK(err == NGPK_E_HDRCRC, "got %s", ngpk_strerror(err));
        CHECK(m.writes == 0 && !m.run_written, "hardware touched");
        free_mock(&m);
        remove(bad);
    }

    /* 4. game too big for the board: refuse before touching anything ----- */
    {
        printf("profile too small\n");
        ngsd_profile_t small = *prof;
        small.slot[NGPK_R_C].cap = 1u * 1024 * 1024; /* below any test game */
        err = run(pack, &small, 4096, &m, &info);
        CHECK(err == NGPK_E_PROFILE, "got %s", ngpk_strerror(err));
        CHECK(m.writes == 0 && m.ctrl_writes == 0 && !m.run_written,
              "hardware touched");
        free_mock(&m);
    }

    /* 4b. C/S in canonical layout: the board needs sdram1 ------------------ */
    if (argc >= 4) {
        printf("wrong layout\n");
        err = run(argv[3], prof, 4096, &m, &info);
        CHECK(err == NGPK_E_LAYOUT, "got %s", ngpk_strerror(err));
        CHECK(m.writes == 0 && m.ctrl_writes == 0 && !m.run_written,
              "hardware touched");
        free_mock(&m);
    }

    /* 5. not an NGPK file at all ------------------------------------------ */
    {
        printf("wrong magic\n");
        const char *bad = "bad_magic.ngpk";
        FILE *o = fopen(bad, "wb");
        for (int i = 0; i < 4096; i++)
            fputc(i & 0xFF, o);
        fclose(o);
        err = run(bad, prof, 4096, &m, &info);
        CHECK(err == NGPK_E_MAGIC, "got %s", ngpk_strerror(err));
        free_mock(&m);
        remove(bad);
    }

    printf(failures ? "\n%d FAILURE(S)\n" : "\nall loader tests passed\n",
           failures);
    return failures ? 1 : 0;
}
