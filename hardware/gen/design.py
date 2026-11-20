"""Minimal netlist model shared by the schematic and PCB writers."""
import collections


class Part:
    def __init__(self, ref, sym, value, footprint, pins, unit_pins=None, props=None):
        self.ref = ref
        self.sym = sym                  # "Lib:Name" (stock) or "NG:Name" (generated)
        self.value = value
        self.footprint = footprint      # "Lib:Name" or None
        self.pins = dict(pins)          # pin number (str) -> net name (str) or None (no connect)
        self.props = props or {}
        self.pos = None                 # PCB placement: (x, y, rot_deg, back)


class Design:
    def __init__(self, name):
        self.name = name
        self.parts = collections.OrderedDict()
        self.custom_symbols = {}        # "NG:Name" -> dict(pins=[(num, name, etype, unit)], ...)
        self.notes = []

    def add(self, part):
        assert part.ref not in self.parts, part.ref
        self.parts[part.ref] = part
        return part

    def nets(self):
        n = collections.OrderedDict()
        for p in self.parts.values():
            for pin, net in p.pins.items():
                if net:
                    n.setdefault(net, []).append((p.ref, pin))
        return n

    def check(self):
        errs = []
        for net, conns in self.nets().items():
            if len(conns) < 2:
                errs.append(f"net {net} has a single connection {conns}")
        return errs
