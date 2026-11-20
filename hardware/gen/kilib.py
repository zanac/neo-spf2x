"""Read symbols from the stock KiCad symbol libraries (s-expression text, no parser deps)."""
import re

SYM_DIR = "/usr/share/kicad/symbols"


def block(s, start):
    d = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return s[start:i + 1]


_cache = {}


def lib_text(lib):
    if lib not in _cache:
        _cache[lib] = open(f"{SYM_DIR}/{lib}.kicad_sym", encoding="utf-8").read()
    return _cache[lib]


def symbol_block(lib, name):
    s = lib_text(lib)
    m = re.search(r'\n  \(symbol "%s"' % re.escape(name), s)
    if not m:
        raise KeyError(f"{lib}:{name}")
    return block(s, m.start() + 1)


def resolve(lib, name):
    """Returns the symbol text with `extends` resolved into a standalone block."""
    b = symbol_block(lib, name)
    m = re.search(r'\(extends "([^"]+)"\)', b)
    if not m:
        return b
    base = resolve(lib, m.group(1))
    # rename the base symbol (and its unit sub-symbols) to the derived name; keep properties of the derived one
    out = base.replace('(symbol "%s"' % m.group(1), '(symbol "%s"' % name, 1)
    out = re.sub(r'\(symbol "%s_(\d+_\d+)"' % re.escape(m.group(1)), r'(symbol "%s_\1"' % name, out)
    # copy derived properties over the base ones
    for pm in re.finditer(r'\(property "([^"]+)" "[^"]*"', b):
        pb = block(b, pm.start())
        key = pm.group(1)
        bm = re.search(r'\(property "%s" "[^"]*"' % re.escape(key), out)
        if bm:
            out = out[:bm.start()] + pb + out[bm.start() + len(block(out, bm.start())):]
    return out


def pins(lib, name):
    b = resolve(lib, name)
    res = []
    for pm in re.finditer(r"\(pin (\w+) (\w+)", b):
        pb = block(b, pm.start())
        res.append(dict(type=pm.group(1),
                        number=re.search(r'\(number "([^"]*)"', pb).group(1),
                        name=re.search(r'\(name "([^"]*)"', pb).group(1)))
    return res


if __name__ == "__main__":
    import sys
    for p in pins(sys.argv[1], sys.argv[2]):
        print(p["number"], p["name"], p["type"])
