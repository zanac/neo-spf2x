#!/usr/bin/env python3
"""Worst-case SDRAM bandwidth/latency model for the cartridge (docs/GATEWARE.md).

Not RTL: a clock-accurate scheduler for a single SDR SDRAM chip (16 bit,
closed-page policy with auto-precharge, 4 banks) serving the traffic classes
the console generates at the same time:

  C   one 8-byte sprite row (burst of 4 words) every 667 ns  (96 sprites/line)
  S   two 16-bit fix reads every 1.33 us                     (40 tiles/line)
  P   one 16-bit 68k read every 333 ns, sequential addresses (4 clk @ 12 MHz)
  M   one byte read every 750 ns (Z80 4 MHz)
  V   ADPCM-A (6 x 9.3 kB/s) + ADPCM-B (27 kB/s) byte reads, random

Rates are upper bounds derived from docs/TIMING.md; deadlines on the console
side are NOT known (open point), so the result is a latency distribution per
class plus total bus utilisation, to be compared with the margins measured
later on a real console.

    python3 gateware/model/sdram_budget.py
"""
import random
import sys
from collections import defaultdict

# AS4C32M16 / MT48LC32M16 class, 133 MHz grade (ns); change for other parts.
PARTS = {
    "133MHz": dict(clk=133.0, cl=3, trcd=20, trp=20, tras=44, trrd=15,
                   trfc=66, trefi=7812),
    "100MHz": dict(clk=100.0, cl=3, trcd=20, trp=20, tras=44, trrd=15,
                   trfc=66, trefi=7812),
}
MiB = 1 << 20


def cyc(ns, mhz):
    return int(-(-ns * mhz // 1000))      # ceil(ns*MHz/1000)


class Req:
    __slots__ = ("cls", "addr", "beats", "t_arr", "t_done", "bank")


def bank_of(addr, mapping):
    if mapping == "top":              # 16 MiB per bank
        return (addr >> 24) & 3
    return (addr >> 11) & 3           # interleave on 2 KiB pages


def simulate(part, mapping="interleave", prio="cfirst", ms=4.0, seed=1,
             c_period=667, with_refresh=True):
    p = PARTS[part]
    f = p["clk"]
    cl, trcd = p["cl"], cyc(p["trcd"], f)
    trc = cyc(p["tras"] + p["trp"], f)
    trrd, trfc = cyc(p["trrd"], f), cyc(p["trfc"], f)
    trefi = cyc(p["trefi"], f)
    ncyc = int(ms * 1e6 * f / 1000)
    rnd = random.Random(seed)

    def ns2c(ns):
        return int(ns * f / 1000)

    # ---- request generators (arrival cycle, class, addr, beats) -----------
    arr = []
    def gen(cls, period_ns, base, size, beats, seq=False, jitter=0):
        t = rnd.randrange(ns2c(period_ns))
        a = base
        while t < ncyc:
            if seq:
                a = base + ((a - base + 2) % size)
            else:
                a = base + (rnd.randrange(size // 8) * 8)
            arr.append((t, cls, a, beats))
            t += ns2c(period_ns) + (rnd.randrange(jitter + 1) if jitter else 0)
    # profile 64M map (docs/ARCHITECTURE.md)
    gen("C", c_period, 0x1A00000, 32 * MiB, 4)
    gen("S", 667, 0x1800000, 128 * 1024, 1)
    gen("S", 667, 0x1800000, 128 * 1024, 1)
    gen("P", 333, 0x0000000, 5 * MiB, 1, seq=True)
    gen("M", 750, 0x1900000, 256 * 1024, 1)
    gen("V", 12000, 0x0800000, 8 * MiB, 1)
    gen("V", 36000, 0x0800000, 8 * MiB, 1)
    arr.sort()

    order = {"cfirst": ["C", "S", "P", "M", "V"],
             "pfirst": ["P", "C", "S", "M", "V"]}[prio]
    rank = {c: i for i, c in enumerate(order)}

    bank_free = [0] * 4
    last_act = -10**9
    data_free = 0
    cmd_busy = set()
    pending = []
    done = []
    i = 0
    next_ref = trefi
    busy_data = 0
    ref_until = 0

    for t in range(ncyc):
        while i < len(arr) and arr[i][0] <= t:
            r = Req()
            r.t_arr, r.cls, r.addr, r.beats = arr[i]
            r.bank = bank_of(r.addr, mapping)
            pending.append(r)
            i += 1
        if with_refresh and t >= next_ref and t >= ref_until:
            # refresh needs every bank idle; delay everything until it is done
            if all(b <= t for b in bank_free):
                ref_until = t + cyc(p["trp"], f) + trfc
                bank_free = [ref_until] * 4
                next_ref += trefi
            else:
                continue                 # stop issuing, drain banks
        if t < ref_until or not pending or t in cmd_busy:
            continue
        if t - last_act < trrd:
            continue
        best = None
        for r in pending:
            if bank_free[r.bank] > t:
                continue
            start = t + trcd + cl
            if start < data_free:
                continue                 # keep data bus conflict-free
            if (t + trcd) in cmd_busy:
                continue
            key = (rank[r.cls], r.t_arr)
            if best is None or key < best[0]:
                best = (key, r)
        if best:
            r = best[1]
            pending.remove(r)
            cmd_busy.add(t + trcd)
            last_act = t
            bank_free[r.bank] = t + trc
            s = t + trcd + cl
            data_free = s + r.beats
            busy_data += r.beats
            r.t_done = s + r.beats
            done.append(r)
        # drop old command-bus markers
        if t % 4096 == 0:
            cmd_busy = {x for x in cmd_busy if x >= t}

    lat = defaultdict(list)
    for r in done:
        lat[r.cls].append((r.t_done - r.t_arr) * 1000.0 / f)
    return lat, len(pending), busy_data / ncyc


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def main():
    print(f"{'part':7} {'map':10} {'prio':7} | data-bus use | worst/p99 latency ns "
          f"(C S P M V) | backlog")
    ok = True
    for part in PARTS:
        for mapping in ("top", "interleave"):
            for prio in ("cfirst", "pfirst"):
                lat, back, util = simulate(part, mapping, prio)
                row = " ".join(f"{max(lat[c]):4.0f}/{pct(lat[c], .99):4.0f}"
                               for c in "CSPMV")
                print(f"{part:7} {mapping:10} {prio:7} | {util*100:5.1f} %      | "
                      f"{row} | {back}")
                if back > 8:
                    ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
