#!/usr/bin/env python3
"""Builds the boot-RAM image the FPGA serves to the 68k while a game loads.

    mkstub.py game_P1_file [--swap16] -o boot.bin [--hex boot.hex]
    mkstub.py --c-header firmware/ngsd_stub_code.h   (regenerate from boot/stub.S)

The image is the first 512 bytes of the game's P region (vectors, 'NEO-GEO'
header, security code) with the eyecatcher flag set to 'draw nothing' and the
USER jump pointed to the stub code at 0x200, plus the stub code (boot/stub.S,
prebuilt in boot/stub.bin) and a ready flag word at 0x3FE.  Mirrors
firmware/ngsd_boot.c (the firmware builds the same image at load time).
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BOOT_BYTES, HEAD, CODE_OFF, FLAG_OFF = 1024, 512, 0x200, 0x3FE


def assemble(src=os.path.join(ROOT, "boot", "stub.S")):
    d = tempfile.mkdtemp()
    o, b = os.path.join(d, "s.o"), os.path.join(d, "s.bin")
    subprocess.run(["m68k-linux-gnu-as", "-m68000", "-o", o, src], check=True)
    subprocess.run(["m68k-linux-gnu-ld", "-Ttext=%#x" % CODE_OFF, "--oformat",
                    "binary", "-o", b, o], check=True, stderr=subprocess.DEVNULL)
    return open(b, "rb").read()


def stub_code():
    return open(os.path.join(ROOT, "boot", "stub.bin"), "rb").read()


def build_image(head, code=None):
    code = code if code is not None else stub_code()
    if len(head) < HEAD:
        raise ValueError("need at least 512 bytes of P region")
    if head[0x100:0x107] != b"NEO-GEO":
        raise ValueError("no NEO-GEO signature at 0x100 (wrong byte order? use --swap16)")
    img = bytearray(BOOT_BYTES)
    img[:HEAD] = head[:HEAD]
    img[0x114] = 2
    img[0x122:0x128] = bytes([0x4E, 0xF9, 0, 0, CODE_OFF >> 8, CODE_OFF & 0xFF])
    img[CODE_OFF:CODE_OFF + len(code)] = code
    return bytes(img)


def c_header(code):
    s = "/* Generated from boot/stub.S by tools/mkstub.py - do not edit. */\n"
    s += "#ifndef NGSD_STUB_CODE_H\n#define NGSD_STUB_CODE_H\n#include <stdint.h>\n"
    s += "#define NGSD_STUB_CODE_LEN %d\n" % len(code)
    s += "static const uint8_t ngsd_stub_code[NGSD_STUB_CODE_LEN] = {\n"
    for i in range(0, len(code), 12):
        s += "    " + ", ".join("0x%02X" % b for b in code[i:i + 12]) + ",\n"
    return s + "};\n#endif\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("p1", nargs="?", help="file with the start of the P region")
    ap.add_argument("--swap16", action="store_true",
                    help="the file is in MAME word-swapped order")
    ap.add_argument("-o", "--output")
    ap.add_argument("--hex", help="also write 16-bit big-endian words, one per line")
    ap.add_argument("--ready", action="store_true",
                    help="set the ready flag (to try the stub in an emulator: it then "
                         "restarts the BIOS in a loop)")
    ap.add_argument("--rebuild-stub", action="store_true",
                    help="re-assemble boot/stub.S (needs m68k binutils)")
    ap.add_argument("--c-header", help="write the firmware stub code header")
    a = ap.parse_args()
    code = assemble() if a.rebuild_stub else stub_code()
    if a.rebuild_stub:
        open(os.path.join(ROOT, "boot", "stub.bin"), "wb").write(code)
    if a.c_header:
        open(a.c_header, "w").write(c_header(code))
    if a.p1:
        head = open(a.p1, "rb").read(HEAD)
        if a.swap16:
            b = bytearray(head)
            b[0::2], b[1::2] = head[1::2], head[0::2]
            head = bytes(b)
        img = bytearray(build_image(head, code))
        if a.ready:
            img[FLAG_OFF:FLAG_OFF + 2] = b"\x00\x01"
        img = bytes(img)
        if a.output:
            open(a.output, "wb").write(img)
        if a.hex:
            with open(a.hex, "w") as f:
                for i in range(0, BOOT_BYTES, 2):
                    f.write("%04x\n" % int.from_bytes(img[i:i + 2], "big"))
        print("boot image: %d bytes, stub code %d bytes at %#x" % (len(img), len(code), CODE_OFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
