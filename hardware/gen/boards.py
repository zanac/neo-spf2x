"""Netlists for the four boards (AES/MVS x CHA/PROG) built from the pin tables.
Everything here is generated; see docs/PCB.md for status and caveats."""
import csv, math, os, re, collections
import design, fpga_db, kilib
from design import Part, Design

HW = os.path.join(os.path.dirname(__file__), "..")
V3, V5, V1, V25, GND = "+3V3", "+5V", "+1V1", "+2V5", "GND"

# --------------------------------------------------------------- signal classes
BIDIR_DIR = {  # bidirectional buses -> name of the FPGA-driven DIR net
    **{f"D{i}": "DIR_D" for i in range(16)},
    **{f"SDRAD{i}": "DIR_SDRAD" for i in range(8)},
    **{f"SDPAD{i}": "DIR_SDPAD" for i in range(8)},
    **{f"SDD{i}": "DIR_SDD" for i in range(8)},
}


def load_signals(fmt):
    f = "signals.csv" if fmt == "aes" else "signals_mvs.csv"
    rows = list(csv.DictReader(open(os.path.join(HW, f))))
    return rows


def load_pins(fmt):
    f = "aes_pins.csv" if fmt == "aes" else "mvs_pins.csv"
    return list(csv.DictReader(open(os.path.join(HW, f))))


def sig_class(sig, d):
    if sig in BIDIR_DIR:
        return BIDIR_DIR[sig]
    return {"in": "IN", "out": "OUT"}.get(d, "IN")     # '4MB' (unknown) is read as an input


# --------------------------------------------------------------- generic helpers
class Builder:
    def __init__(self, name):
        self.d = Design(name)
        self.n = collections.Counter()

    def ref(self, prefix):
        self.n[prefix] += 1
        return f"{prefix}{self.n[prefix]}"

    def add(self, prefix, sym, value, fp, pins, **kw):
        return self.d.add(Part(self.ref(prefix), sym, value, fp, pins, **kw))

    def r(self, a, b, val="10k"):
        return self.add("R", "Device:R", val, "Resistor_SMD:R_0402_1005Metric", {"1": a, "2": b})

    def c(self, a, b, val="100n", fp="Capacitor_SMD:C_0402_1005Metric"):
        return self.add("C", "Device:C", val, fp, {"1": a, "2": b})

    def stock(self, prefix, lib, name, value, fp, nets, default=None):
        pins = {p["number"]: default for p in kilib.pins(lib, name)}
        for num, net in nets.items():
            assert num in pins, (name, num)
            pins[num] = net
        return self.add(prefix, f"{lib}:{name}", value, fp, pins)


def custom(d, name, units, ref="U", width=20.32):
    d.custom_symbols[f"NG:{name}"] = dict(units=units, ref=ref, width=width)
    return f"NG:{name}"


# --------------------------------------------------------------- 16-bit translator
T16 = {  # SN74ALVC164245DGG (TSSOP-48), A = 3.3 V side (FPGA), B = 5 V side (console)
    "1DIR": 1, "1OE": 48, "2DIR": 24, "2OE": 25,
    **{f"1B{i+1}": n for i, n in enumerate((2, 3, 5, 6, 8, 9, 11, 12))},
    **{f"2B{i+1}": n for i, n in enumerate((13, 14, 16, 17, 19, 20, 22, 23))},
    **{f"1A{i+1}": n for i, n in enumerate((47, 46, 44, 43, 41, 40, 38, 37))},
    **{f"2A{i+1}": n for i, n in enumerate((36, 35, 33, 32, 30, 29, 27, 26))},
}
T16_GND = (4, 10, 15, 21, 28, 34, 39, 45)
T16_VCCB = (7, 18)
T16_VCCA = (31, 42)


def t16_symbol(d):
    if "NG:SN74ALVC164245" in d.custom_symbols:
        return "NG:SN74ALVC164245"
    units = {}
    for u in (1, 2):
        pl = [dict(number=str(T16[f"{u}A{i}"]), name=f"{u}A{i}", etype="bidirectional", side="L") for i in range(1, 9)]
        pl += [dict(number=str(T16[f"{u}DIR"]), name=f"{u}DIR", etype="input", side="L"),
               dict(number=str(T16[f"{u}OE"]), name=f"{u}~{{OE}}", etype="input", side="L")]
        pr = [dict(number=str(T16[f"{u}B{i}"]), name=f"{u}B{i}", etype="bidirectional", side="R") for i in range(1, 9)]
        units[u] = pl + pr
    units[3] = ([dict(number=str(n), name="GND", etype="power_in", side="L") for n in T16_GND] +
                [dict(number=str(n), name="VCCA", etype="power_in", side="R") for n in T16_VCCA] +
                [dict(number=str(n), name="VCCB", etype="power_in", side="R") for n in T16_VCCB])
    return custom(d, "SN74ALVC164245", units)


def add_translators(b, sigs, oe_net, edge_net, fpga_net):
    """sigs: list of (signal, class).  Groups of 8 of the same class; two groups per chip.
    edge_net(sig) -> B-side net (console), fpga_net(sig) -> A-side net (3.3 V).
    returns the list of per-group info (for placement)."""
    by = collections.OrderedDict()
    for s, c in sigs:
        by.setdefault(c, []).append(s)
    groups = []
    for c, lst in by.items():
        for i in range(0, len(lst), 8):
            groups.append((c, lst[i:i + 8]))
    sym = t16_symbol(b.d)
    chips = []
    for i in range(0, len(groups), 2):
        pins = {str(n): GND for n in T16_GND}
        pins.update({str(n): V3 for n in T16_VCCA})
        pins.update({str(n): V5 for n in T16_VCCB})
        for u, (c, lst) in zip((1, 2), groups[i:i + 2]):
            pins[str(T16[f"{u}OE"])] = oe_net
            pins[str(T16[f"{u}DIR"])] = {"IN": GND, "OUT": V3}.get(c, c)
            for k in range(8):
                if k < len(lst):
                    pins[str(T16[f"{u}A{k+1}"])] = fpga_net(lst[k])
                    pins[str(T16[f"{u}B{k+1}"])] = edge_net(lst[k])
                else:               # unused channel: the input side must not float (data I/Os are always active,
                    # SCAS416P function table note 1) and the direction may be either: both sides to GND is safe
                    pins[str(T16[f"{u}A{k+1}"])] = GND
                    pins[str(T16[f"{u}B{k+1}"])] = GND
        if len(groups[i:i + 2]) == 1:      # the second half of the chip is unused
            pins[str(T16["2OE"])] = V3
            pins[str(T16["2DIR"])] = GND
            for k in range(8):
                pins[str(T16[f"2A{k+1}"])] = GND
                pins[str(T16[f"2B{k+1}"])] = GND
        p = b.add("U", sym, "SN74ALVC164245DGG", "Package_SO:TSSOP-48_6.1x12.5mm_P0.5mm", pins)
        chips.append(p)
    # bypass: one 100 nF per supply pin pair
    for _ in chips:
        for rail in (V3, V3, V5, V5):
            b.c(rail, GND)
    return groups, chips


# --------------------------------------------------------------- edge connector
def edge_symbol(d, name, npins):
    pl = [dict(number=str(i + 1), name=f"{i+1}", etype="passive", side="L") for i in range(npins)]
    return custom(d, name, {1: pl}, ref="J", width=7.62)


def add_edge(b, fmt, board, edge_net):
    pins = [r for r in load_pins(fmt) if r["board"] == board]
    res = {}
    for side in ("A", "B"):
        rows = sorted((r for r in pins if r["side"] == side), key=lambda r: int(r["pin"]))
        n = len(rows)
        sym = edge_symbol(b.d, f"EDGE_{fmt.upper()}_{side}", n)
        nets = {}
        for r in rows:
            nets[r["pin"]] = edge_net(r["signal"])
        b.add("J", sym, f"{fmt.upper()} {board} edge {side}", f"NG:neogeo-{fmt}-{side.lower()}-side-edge", nets)
    return res


# --------------------------------------------------------------- FPGA
FPGA_CFG_FIXED = {  # SPI-flash master configuration (balls from the Lattice CSV)
    "AE2": "FLASH_DI", "AD2": "FLASH_DO", "AF2": "FLASH_IO2", "AE1": "FLASH_IO3",
    "AA2": "FLASH_CS_N", "AE3": "FLASH_CLK",
}
NOGO_DUAL = ("MCLK", "CSN", "CS1N", "SN", "WRITEN", "DOUT", "BUSY", "HOLDN", "DI", "D0", "D1", "D2", "D3",
             "D4", "D5", "D6", "D7", "DEBUG", "CSSPIN", "CSON", "MOSI", "MISO", "CCLK", "DQ")


def usable_gpio(balls):
    out = {}
    for k, v in balls.items():
        if v["kind"] != "gpio" or v["bank"] == "8" or k in FPGA_CFG_FIXED:
            continue
        dual = v["dual"]
        if any(tok in dual.replace("/", " ").replace("_", " ").split() for tok in
               ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "MOSI", "MISO", "CSSPIN", "CS1N", "CSN", "SN",
                "WRITEN", "DOUT", "BUSY", "HOLDN", "DI", "MCLK", "DEBUG", "CCLK")):
            continue
        out[k] = v
    return out


def edge_of(v):
    return v["func"][:2]            # PL PR PT PB


def order_key(ball, v):
    r, c = fpga_db.pos(ball)
    e = edge_of(v)
    return (r if e in ("PL", "PR") else c)


def assign_balls(groups_by_edge, balls, extra_clock=()):
    """groups_by_edge: list of (preferred edges tuple, [signals]).  Greedy sequential along edges."""
    free = usable_gpio(balls)
    lists = {}
    for e in ("PL", "PR", "PT"):
        lists[e] = sorted((k for k, v in free.items() if edge_of(v) == e), key=lambda k: order_key(k, free[k]))
    # last resort: bank-8 balls that double as configuration pins (usable as I/O after configuration;
    # their translators stay disabled by the pulled-up OE until the FPGA is running)
    lists["PB"] = sorted((k for k, v in balls.items() if v["kind"] == "gpio" and v["bank"] == "8"
                          and k not in FPGA_CFG_FIXED), key=lambda k: fpga_db.pos(k))
    assign = {}
    # clock inputs first on PCLK-capable balls
    for sig in extra_clock:
        for e in ("PT", "PL", "PR"):
            # the PLL reference (24M) must sit on a dedicated PLL input (xxx_GPLLnT_IN, TN-02200 7.1/18.2.1);
            # the other clocks only need to be PCLK-capable
            want = "GPLL" if sig == "24M" else "PCLK"
            cand = [k for k in lists[e] if want in free[k]["dual"] and (want != "GPLL" or "T_IN" in free[k]["dual"])]
            if cand:
                assign[sig] = cand[0]
                lists[e].remove(cand[0])
                break
        else:
            raise RuntimeError("no clock ball for " + sig)
    for prefs, sigs in groups_by_edge:
        for s in sigs:
            for e in prefs + tuple(x for x in ("PL", "PR", "PT", "PB") if x not in prefs):
                if lists[e]:
                    assign[s] = lists[e].pop(0)
                    break
            else:
                raise RuntimeError("out of FPGA I/O at " + s)
    return assign, free


def fpga_part(b, balls, assign, extra_nets):
    """Builds the FPGA symbol (units per bank/function) and the part."""
    inv = {v: k for k, v in assign.items()}
    units, pins = {}, {}
    banks = sorted({v["bank"] for v in balls.values() if v["kind"] == "gpio"})
    ubank = {bk: i + 1 for i, bk in enumerate(banks)}
    upwr, ucfg = len(banks) + 1, len(banks) + 2
    for ball in sorted(balls, key=lambda k: (fpga_db.pos(k))):
        v = balls[ball]
        name = v["func"] + (("/" + v["dual"]) if v["dual"] not in ("-", "") else "")
        if v["kind"] == "gpio":
            u, et = ubank[v["bank"]], "bidirectional"
            net = inv.get(ball) or extra_nets.get(ball)
        elif v["kind"] in ("power", "vccio", "gnd"):
            u, et = upwr, "power_in"
            net = {"VCC": V1, "VCCAUX": "VCCAUX_F"}.get(v["func"], GND if v["kind"] == "gnd" else V3)
        else:
            u, et = ucfg, "passive"
            net = extra_nets.get(ball)          # None -> no-connect
        units.setdefault(u, []).append(dict(number=ball, name=name, etype=et, side="L" if len(units.get(u, [])) % 2 == 0 else "R"))
        pins[ball] = net
    # balance sides: first half left, second half right
    for u, pl in units.items():
        h = (len(pl) + 1) // 2
        for i, p in enumerate(pl):
            p["side"] = "L" if i < h else "R"
    sym = custom(b.d, "LFE5U-45F-BGA554", units, width=30.48)
    return b.add("U", sym, "LFE5U-45F-8BG554", "NG:BGA-554_26x26_23.0x23.0mm_P0.8mm", pins)


def fpga_decoupling(b, balls):
    """TN-02038 Table 3.1: VCC 3 x 10 uF + 100 nF per pin; VCCAUX 120 ohm ferrite + 10 uF + 100 nF per pin;
    VCCIO 10 uF per bank + 100 nF per pin (all VCCIO banks used here, all at 3.3 V)."""
    C10 = "Capacitor_SMD:C_0603_1608Metric"
    n_vcc = sum(1 for v in balls.values() if v["func"] == "VCC")
    n_aux = sum(1 for v in balls.values() if v["func"] == "VCCAUX")
    banks = sorted({v["bank"] for v in balls.values() if v["func"].startswith("VCCIO")})
    n_io = sum(1 for v in balls.values() if v["func"].startswith("VCCIO"))
    for _ in range(n_vcc):
        b.c(V1, GND)
    for _ in range(3):
        b.c(V1, GND, "10u", C10)
    b.add("FB", "Device:FerriteBead", "120R@100MHz", "Inductor_SMD:L_0603_1608Metric", {"1": V25, "2": "VCCAUX_F"})
    for _ in range(n_aux):
        b.c("VCCAUX_F", GND)
    b.c("VCCAUX_F", GND, "10u", C10)
    for _ in range(n_io):
        b.c(V3, GND)
    for _ in banks:
        b.c(V3, GND, "10u", C10)


# --------------------------------------------------------------- SDRAM (512 Mbit x16, TSOP-II-54)
SDR_PINS = {  # pin -> name   (standard x16 SDR pinout)
    1: "VDD", 2: "DQ0", 3: "VDDQ", 4: "DQ1", 5: "DQ2", 6: "VSSQ", 7: "DQ3", 8: "DQ4", 9: "VDDQ", 10: "DQ5",
    11: "DQ6", 12: "VSSQ", 13: "DQ7", 14: "VDD", 15: "LDQM", 16: "WE#", 17: "CAS#", 18: "RAS#", 19: "CS#",
    20: "BA0", 21: "BA1", 22: "A10", 23: "A0", 24: "A1", 25: "A2", 26: "A3", 27: "VDD", 28: "VSS", 29: "A4",
    30: "A5", 31: "A6", 32: "A7", 33: "A8", 34: "A9", 35: "A11", 36: "A12", 37: "CKE", 38: "CLK", 39: "UDQM",
    40: "NC", 41: "VSS", 42: "DQ8", 43: "VDDQ", 44: "DQ9", 45: "DQ10", 46: "VSSQ", 47: "DQ11", 48: "DQ12",
    49: "VDDQ", 50: "DQ13", 51: "DQ14", 52: "VSSQ", 53: "DQ15", 54: "VSS"}
SDR_NET = {"WE#": "SDR_WE_N", "CAS#": "SDR_CAS_N", "RAS#": "SDR_RAS_N", "LDQM": "SDR_DQM0",
           "UDQM": "SDR_DQM1", "CLK": "SDR_CLK", "BA0": "SDR_BA0", "BA1": "SDR_BA1"}


def add_sdram(b, cs_net):
    pins, left, right = {}, [], []
    for n, nm in SDR_PINS.items():
        if nm in ("VDD", "VDDQ"):
            net, et = V3, "power_in"
        elif nm in ("VSS", "VSSQ"):
            net, et = GND, "power_in"
        elif nm == "NC":
            net, et = None, "no_connect"
        elif nm == "CKE":
            net, et = "SDR_CKE", "input"      # driven by the FPGA: low at power-up (datasheet note 11)
        elif nm.startswith("DQ"):
            net, et = f"SDR_DQ{nm[2:]}", "bidirectional"
        elif nm.startswith("A"):
            net, et = f"SDR_A{nm[1:]}", "input"
        elif nm == "CS#":
            net, et = cs_net, "input"
        else:
            net, et = SDR_NET[nm], "input"
        pins[str(n)] = net
        (left if n <= 27 else right).append(dict(number=str(n), name=nm, etype=et, side="L" if n <= 27 else "R"))
    sym = custom(b.d, "SDRAM_512M_X16_TSOPII54", {1: left + right})
    b.add("U", sym, "AS4C32M16SB / IS42S16320D (512Mbit x16)", "Package_SO:TSOP-II-54_22.2x10.16mm_P0.8mm", pins)
    # power-up (AS4C32M16SB note 11): CKE low and DQM high while the FPGA I/O is still tri-stated
    b.r("SDR_CKE", GND, "10k"); b.r("SDR_DQM0", V3, "10k"); b.r("SDR_DQM1", V3, "10k")
    for _ in range(8):
        b.c(V3, GND)
    b.c(V3, GND, "10u", "Capacitor_SMD:C_0805_2012Metric")


# --------------------------------------------------------------- power
def add_power_cha(b):
    # 5 V (console) -> 3.3 V buck (TLV62569, 2 A); 2.5 V (VCCAUX) and 1.1 V (VCC) bucks both fed from the 3.3 V rail,
    # so VCCIO (3.3 V) always rises before VCCAUX and VCC (TN-02038 sec. 4: VCCIO before or together with them).
    # A linear 3.3 V from 5 V would dissipate (5 - 3.3) * ~0.7 A = 1.2 W in a SOT-223 (90 C/W).
    # TLV62569 (SOT-23-5: 1 EN, 2 GND, 3 SW, 4 VIN, 5 FB), Vout = 0.6 (1 + R1/R2); L 2.2 uH, Cout 2 x 22 uF
    sym = custom(b.d, "BUCK_ADJ_SOT23_5", {1: [
        dict(number="4", name="VIN", etype="power_in", side="L"), dict(number="1", name="EN", etype="input", side="L"),
        dict(number="2", name="GND", etype="power_in", side="L"), dict(number="3", name="SW", etype="output", side="R"),
        dict(number="5", name="FB", etype="input", side="R")]})
    ind = "Inductor_SMD:L_Taiyo-Yuden_NR-40xx"
    b.add("U", sym, "TLV62569", "Package_TO_SOT_SMD:SOT-23-5", {"4": V5, "1": V5, "2": GND, "3": "BUCK33_SW", "5": "BUCK33_FB"})
    b.add("L", "Device:L", "2.2uH NRS4018T2R2MDGJV", ind, {"1": "BUCK33_SW", "2": V3})
    b.r(V3, "BUCK33_FB", "453k")
    b.r("BUCK33_FB", GND, "100k")              # 0.6 * (1 + 453/100) = 3.32 V
    b.c(V5, GND, "10u", "Capacitor_SMD:C_0805_2012Metric")
    for _ in range(2):
        b.c(V3, GND, "22u", "Capacitor_SMD:C_1206_3216Metric")
    b.add("U", sym, "TLV62569", "Package_TO_SOT_SMD:SOT-23-5", {"4": V3, "1": V3, "2": GND, "3": "BUCK_SW", "5": "BUCK_FB"})
    b.add("L", "Device:L", "2.2uH NRS4018T2R2MDGJV", ind, {"1": "BUCK_SW", "2": V1})
    b.r(V1, "BUCK_FB", "10k")
    b.r("BUCK_FB", GND, "12k")                 # 0.6 * (1 + 10/12) = 1.10 V
    for _ in range(2):
        b.c(V1, GND, "22u", "Capacitor_SMD:C_1206_3216Metric")
    b.add("U", sym, "TLV62569", "Package_TO_SOT_SMD:SOT-23-5", {"4": V3, "1": V3, "2": GND, "3": "BUCK25_SW", "5": "BUCK25_FB"})
    b.add("L", "Device:L", "2.2uH NRS4018T2R2MDGJV", ind, {"1": "BUCK25_SW", "2": V25})
    b.r(V25, "BUCK25_FB", "316k")
    b.r("BUCK25_FB", GND, "100k")              # 0.6 * (1 + 316/100) = 2.496 V (VFB 0.588-0.612 V, 1 % resistors)
    for _ in range(2):
        b.c(V25, GND, "22u", "Capacitor_SMD:C_1206_3216Metric")
    b.c(V3, GND, "10u", "Capacitor_SMD:C_0805_2012Metric")


# --------------------------------------------------------------- link connector (PROG <-> CHA)
LINK_N = 80


def link_signals(fmt):
    rows = load_signals(fmt)
    prog = []
    for r in rows:
        if r["board"] == "PROG" and r["signal"] not in prog:
            prog.append(r["signal"])
    return prog


SPI_NETS = ["SPI_SCLK", "SPI_CS_N", "SPI_IO0", "SPI_IO1", "SPI_IO2", "SPI_IO3"]
CTL_NETS = ["OE_PRG_N", "MCU_RUN", "MCU_INT"]


def link_pin_map(fmt):
    """pin number (1..80, plus 81..160 for the second connector) -> net"""
    sigs = link_signals(fmt)
    if fmt == "mvs":        # RESET / SLOTCS are taken from the CHA copy
        sigs = [s for s in sigs if s not in ("RESET", "SLOTCS")]
    dirs = sorted({v for v in BIDIR_DIR.values()})
    nets = sigs + SPI_NETS + CTL_NETS + [x for x in dirs if x in {BIDIR_DIR[s] for s in sigs if s in BIDIR_DIR}]
    m = {}
    gnd_every = 4
    pin, k = 1, 0
    # J1 (pins 1-80) signals interleaved with ground; J2 (81-160) as overflow, power at the end
    pins = []
    for n in nets:
        pins.append(n)
        if len(pins) % gnd_every == 3:
            pins.append(GND)
    assert len(pins) + 6 <= 2 * LINK_N, len(pins)
    pins += [V3, V3, V3, V5, V5, GND]
    for i, n in enumerate(pins):
        m[i + 1] = n
    for i in range(len(pins) + 1, 2 * LINK_N + 1):
        m[i] = GND
    return m


LINK_FP_CHA = "NG:Hirose_DF12NB3.0-80DS-0.5V51_2x40_P0.50mm_Vertical"           # receptacle, 3.0 mm mated
LINK_FP_PROG = "NG:Hirose_DF12NB3.0-80DP-0.5V51_2x40_P0.50mm_Vertical"   # plug


def add_link(b, fmt, side):
    m = link_pin_map(fmt)
    fp = LINK_FP_CHA if side == "CHA" else LINK_FP_PROG
    for j in (0, 1):
        sym = edge_symbol(b.d, "LINK_2x40", LINK_N)
        b.add("J", sym, f"LINK{j+1}", fp, {str(i): m[j * LINK_N + i] for i in range(1, LINK_N + 1)})


# --------------------------------------------------------------- CHA board
def build_cha(fmt):
    b = Builder(f"{fmt}_cha")
    sigs = load_signals(fmt)
    cha = [(r["signal"], sig_class(r["signal"], r["dir_guess"])) for r in sigs if r["board"] == "CHA"]
    prog = [s for s in link_pin_map(fmt).values() if s not in (GND, V3, V5)]
    cha_names = {s for s, _ in cha}
    balls = fpga_db.load()

    clocks = [s for s in ("24M", "12M", "8M", "68KCLKB") if s in cha_names or s in prog]
    sdr = ([f"SDR_A{i}" for i in range(13)] + ["SDR_BA0", "SDR_BA1"] + [f"SDR_DQ{i}" for i in range(16)] +
           ["SDR_DQM0", "SDR_DQM1", "SDR_CKE", "SDR_CLK", "SDR_CS0_N", "SDR_CS1_N", "SDR_RAS_N", "SDR_CAS_N", "SDR_WE_N"])
    dirs = sorted({BIDIR_DIR[s] for s, _ in cha if s in BIDIR_DIR})
    cha_sig = [s for s, _ in cha if s not in clocks]
    groups = [(("PL",), sdr), (("PL",), SPI_NETS + ["MCU_RUN", "MCU_INT"]),
              (("PT", "PR"), cha_sig), (("PT", "PR"), ["OE_CHA_N"] + dirs),
              (("PR", "PB", "PL"), [p for p in prog if p not in clocks and p not in SPI_NETS and p not in CTL_NETS and p not in dirs and p not in cha_names]),
              (("PR",), ["OE_PRG_N"])]
    for dn in dirs:                                 # a DIR shared with PROG is also on the link
        pass
    assign, free = assign_balls(groups, balls, extra_clock=clocks)
    extra = {}
    # configuration
    extra.update(FPGA_CFG_FIXED)
    extra["AE3"] = "FLASH_CLK_F"       # MCLK: 33 ohm series resistor near the FPGA (TN-02038 Table 6.2 note 1: 22-80 ohm)
    extra.update({"AF3": "FPGA_INITN", "AB4": "FPGA_PROGRAMN", "AC4": "FPGA_DONE", "AB5": "JTAG_TDO",
                  "AD5": "JTAG_TCK", "AC5": "JTAG_TDI", "AE5": "JTAG_TMS", "AE4": "CFG1", "AD4": "CFG2", "AF4": "CFG0"})
    fp = fpga_part(b, balls, assign, extra)
    fpga_decoupling(b, balls)
    # CFGMDN[2:0] = 010 = Master SPI (TN-02039 Table 4.5/4.6).  Pins have weak internal pull-ups: a 0 needs an
    # external pull-down < 500 ohm (sec. 4.6.1), a 1 a 4.7k pull-up
    # TN-02038 Fig. 6.1/6.2: 4.7k pull-ups to VCCIO8 on all three, a 0 ohm strap to GND for the zeros
    for n in ("CFG0", "CFG1", "CFG2"):
        b.r(n, V3, "4.7k")
    b.r("CFG0", GND, "0"); b.r("CFG2", GND, "0")
    # TN1269 hardware checklist: 4.7k pull-ups to VCCIO8 on INITN/PROGRAMN, JTAG TCK pull-down,
    # TDI/TMS/TDO pull-ups (values rechecked against TN-02039); flash IO2 (WP) / IO3 (HOLD) held high for x1 mode
    for n in ("FPGA_INITN", "FPGA_PROGRAMN", "FPGA_DONE", "JTAG_TDI", "JTAG_TMS", "JTAG_TDO"):
        b.r(n, V3, "4.7k")
    b.r("JTAG_TCK", GND, "4.7k")
    # TN-02039 Table 4.5 notes 2, 4, 6 and Table 6.1: CSSPIN 4.7k pull-up, MOSI/MISO 10k pull-ups, MCLK 1k pull-up
    b.r("FLASH_CLK", V3, "1k"); b.r("FLASH_CLK_F", "FLASH_CLK", "33")
    b.r("FLASH_DI", V3, "10k"); b.r("FLASH_DO", V3, "10k")
    for n in ("FLASH_IO2", "FLASH_IO3"):
        b.r(n, V3, "10k")
    b.r("FLASH_CS_N", V3, "4.7k")
    for n in ("OE_CHA_N", "OE_PRG_N"):
        b.r(n, V3, "10k")
    for n in dirs:                                  # DIR floats while the FPGA is not configured: keep B->A (OE is high anyway)
        b.r(n, GND, "10k")
    b.r("SPI_CS_N", V3, "10k")
    b.add("D", "Device:LED", "DONE", "LED_SMD:LED_0603_1608Metric", {"1": "LED_K", "2": "LED_A"})
    b.r("LED_A", "FPGA_DONE", "1k"); b.r("LED_K", GND, "0")
    b.add("SW", "Switch:SW_Push", "PROGRAMN", "Button_Switch_SMD:SW_SPST_PTS810", {"1": "FPGA_PROGRAMN", "2": GND})
    jt = b.stock("J", "Connector_Generic", "Conn_02x05_Odd_Even", "JTAG", "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
                 {"1": V3, "2": "JTAG_TMS", "3": GND, "4": "JTAG_TCK", "5": GND, "6": "JTAG_TDO", "8": "JTAG_TDI", "9": GND},   # ARM Cortex Debug 10-pin 1.27 mm (Tigard, J-Link, ...)
                 default=None)
    # SPI flash
    b.stock("U", "Memory_Flash", "W25Q128JVS", "W25Q128JVS", "Package_SO:SOIC-8W_5.3x5.3mm_P1.27mm",
            {"1": "FLASH_CS_N", "2": "FLASH_DO", "3": "FLASH_IO2", "4": GND, "5": "FLASH_DI", "6": "FLASH_CLK",
             "7": "FLASH_IO3", "8": V3})
    b.c(V3, GND)
    add_sdram(b, "SDR_CS0_N")
    add_sdram(b, "SDR_CS1_N")        # second chip: 128 MiB (ngsd-128M); may be left unpopulated
    b.r("SDR_CS1_N", V3, "10k")      # deselected when absent / FPGA not configured
    b.r("SDR_CS0_N", V3, "10k")
    add_power_cha(b)
    # console translators (CHA fingers)
    def edge_net(s):
        return f"X_{s}"
    groups_t, chips = add_translators(b, [(s, c) for s, c in cha if s not in ("RESET",) or True], "OE_CHA_N",
                                      lambda s: edge_net(s), lambda s: s)
    # the clocks are inputs straight into the FPGA through the translators too (same nets)
    add_edge(b, fmt, "CHA", lambda sig: {"GND": GND, "VCC": V5}.get(sig, f"X_{sig}" if sig in cha_names else None))
    add_link(b, fmt, "CHA")
    # DIR nets also feed the PROG translators through the link: nothing else to add
    return clean(b.d), {k.replace('/', '_'): v for k, v in assign.items()}


# --------------------------------------------------------------- PROG board
def build_prog(fmt):
    b = Builder(f"{fmt}_prog")
    rows = load_signals(fmt)
    prog = []
    for r in rows:
        if r["board"] == "PROG" and not (fmt == "mvs" and r["signal"] in ("RESET", "SLOTCS")):
            prog.append((r["signal"], sig_class(r["signal"], r["dir_guess"])))
    names = {s for s, _ in prog}
    add_translators(b, prog, "OE_PRG_N", lambda s: f"X_{s}", lambda s: s)
    add_edge(b, fmt, "PROG", lambda sig: {"GND": GND, "VCC": V5}.get(sig, f"X_{sig}" if sig in names else None))
    add_link(b, fmt, "PROG")
    for rail in (V5, V3):
        b.c(rail, GND, "22u", "Capacitor_SMD:C_1206_3216Metric")
    # microSD
    sd = {"1": "SD_D2", "2": "SD_D3", "3": "SD_CMD", "4": V3, "5": "SD_CLK", "6": GND, "7": "SD_D0", "8": "SD_D1",
          "9": "SD_DET", "10": GND, "11": GND}
    b.stock("J", "Connector", "Micro_SD_Card_Det_Hirose_DM3AT", "microSD", "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5", sd)
    for n in ("SD_D0", "SD_D1", "SD_D2", "SD_D3", "SD_CMD"):
        b.r(n, V3, "47k")
    # RP2040
    rp = {"1": V3, "10": V3, "22": V3, "33": V3, "42": V3, "49": V3, "43": V3, "44": V3, "48": V3,
          "23": "RP_DVDD", "50": "RP_DVDD", "45": "RP_DVDD", "57": GND, "19": GND,
          "20": "XIN", "21": "XOUT", "26": "RP_RUN", "24": "SWCLK", "25": "SWD",
          "46": "USB_DM_R", "47": "USB_DP_R",
          "51": "QSPI_SD3", "52": "QSPI_SCLK", "53": "QSPI_SD0", "54": "QSPI_SD2", "55": "QSPI_SD1", "56": "QSPI_SS",
          # SPI/quad link to the FPGA on GPIO0-5, SD on GPIO6-11, control on 12-14, LED 25
          "2": "SPI_SCLK", "3": "SPI_CS_N", "4": "SPI_IO0", "5": "SPI_IO1", "6": "SPI_IO2", "7": "SPI_IO3",
          "8": "SD_CLK", "9": "SD_CMD", "11": "SD_D0", "12": "SD_D1", "13": "SD_D2", "14": "SD_D3",
          "15": "SD_DET", "16": "MCU_RUN", "17": "MCU_INT", "37": "LED_MCU"}
    b.stock("U", "MCU_RaspberryPi", "RP2040", "RP2040", "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm", rp)
    for _ in range(10):
        b.c(V3, GND)
    b.c("RP_DVDD", GND, "1u"); b.c("RP_DVDD", GND, "100n"); b.c(V3, GND, "1u")
    b.r("RP_RUN", V3, "10k")
    b.add("SW", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_PTS810", {"1": "RP_RUN", "2": GND})
    b.add("SW", "Switch:SW_Push", "BOOTSEL", "Button_Switch_SMD:SW_SPST_PTS810", {"1": "BOOTSEL_N", "2": GND})
    b.r("BOOTSEL_N", "QSPI_SS", "1k")
    b.r("USB_DM_R", "USB_DM", "27"); b.r("USB_DP_R", "USB_DP", "27")
    b.stock("J", "Connector_Generic", "Conn_01x04", "USB/SWD pads", "Connector_PinHeader_1.27mm:PinHeader_1x04_P1.27mm_Vertical",
            {"1": "USB_DM", "2": "USB_DP", "3": GND, "4": V5})
    b.stock("J", "Connector_Generic", "Conn_01x03", "SWD", "Connector_PinHeader_1.27mm:PinHeader_1x03_P1.27mm_Vertical",
            {"1": "SWCLK", "2": GND, "3": "SWD"})
    # 12 MHz crystal
    b.add("Y", "Device:Crystal_GND24", "12MHz ABM8-272-T3", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
          {"1": "XIN", "2": GND, "3": "XOUT_R", "4": GND})
    b.r("XOUT", "XOUT_R", "1k")
    b.c("XIN", GND, "15p"); b.c("XOUT_R", GND, "15p")
    # QSPI boot flash
    b.stock("U", "Memory_Flash", "W25Q128JVS", "W25Q128JVS", "Package_SO:SOIC-8W_5.3x5.3mm_P1.27mm",
            {"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": GND, "5": "QSPI_SD0", "6": "QSPI_SCLK",
             "7": "QSPI_SD3", "8": V3})
    b.c(V3, GND)
    b.add("D", "Device:LED", "MCU", "LED_SMD:LED_0603_1608Metric", {"1": "LED_K", "2": "LED_A"})
    b.r("LED_A", "LED_MCU", "1k"); b.r("LED_K", GND, "0")
    return clean(b.d)


def clean(d):
    """'/' is the hierarchy separator in KiCad net names (R/W -> R_W)."""
    for p in d.parts.values():
        p.pins = {k: (v.replace("/", "_") if v else v) for k, v in p.pins.items()}
    return d


if __name__ == "__main__":
    import sys
    for fmt in ("aes", "mvs"):
        d, assign = build_cha(fmt)
        p = build_prog(fmt)
        for name, dd in ((f"{fmt}_cha", d), (f"{fmt}_prog", p)):
            errs = dd.check()
            print(name, len(dd.parts), "parts", len(dd.nets()), "nets;", len(errs), "single-pin nets")
            for e in errs[:8]:
                print("   ", e)
        print(fmt, "FPGA I/O used:", len(assign))
