CC      ?= gcc
CFLAGS  ?= -std=c99 -O1 -g -Wall -Wextra -Werror -pedantic
SAN     ?= -fsanitize=address,undefined

SRC = ngpk.c ngsd_loader.c ngsd_boot.c

# Usage:
#   make test PACK=game.ngpk UNPACKED=dir [CANON=x.ngpk BOOT=expected_boot.bin]      (dir from `ngpk.py unpack`)
# or simply run ../tests/run_all.sh, which builds the inputs for you.
test_loader: $(SRC) test/test_loader.c ngpk.h ngsd_loader.h ngsd_boot.h ngsd_stub_code.h
	$(CC) $(CFLAGS) $(SAN) -o $@ $(SRC) test/test_loader.c

test: test_loader
	./test_loader $(PACK) $(UNPACKED) $(CANON) $(BOOT)

test_sd: sd_spi.c sd_spi.h test/test_sd.c
	$(CC) $(CFLAGS) $(SAN) -o $@ sd_spi.c test/test_sd.c

check_sd: test_sd
	./test_sd

clean:
	rm -f test_loader test_sd bad_*.ngpk

.PHONY: test check_sd clean
