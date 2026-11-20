"""Round-trip check: Design -> .kicad_sch -> kicad-cli netlist must give the same nets.
(KiCad 7 has no CLI ERC, so this is the connectivity check for generated schematics.)"""
import re, subprocess, sys, tempfile, os
import design, kisch


def netlist_of(sch):
    out = sch + ".net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", sch, "-o", out], check=True,
                   capture_output=True)
    txt = open(out).read()
    nets = {}
    for chunk in txt.split("(net (code ")[1:]:
        name = re.search(r'\(name "/?([^"]*)"\)', chunk).group(1)
        nets[name] = sorted(re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', chunk))
    return nets


def check(d):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "x.kicad_sch")
        kisch.write(d, p, d.name)
        got = netlist_of(p)
    want = {n: sorted(c) for n, c in d.nets().items()}
    bad = [n for n in want if got.get(n) != want[n]]
    return bad


if __name__ == "__main__":
    d = design.Design("selftest")
    for r in ("R1", "R2", "R3"):
        d.add(design.Part(r, "Device:R", "10k", "Resistor_SMD:R_0402", {"1": "A", "2": "B"}))
    bad = check(d)
    print("selftest:", "OK" if not bad else bad)
    sys.exit(bool(bad))
