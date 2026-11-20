#!/usr/bin/env python3
"""Checks that the English docs (README.md, docs/*.md) and the Italian ones
(README.it.md, docs/it/*.md) stay in step: same file set and same structure
(headings per level, table rows, list items, fenced code blocks, backticked file paths).
It cannot judge translation quality: it catches a file or section that was
updated in one language only.

    python3 -I tests/check_docs.py
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def read(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def structure(text):
    fences = re.findall(r"^```(\w*)", text, flags=re.M)
    body = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    heads = [len(m) for m in re.findall(r"^(#{1,6}) ", body, flags=re.M)]
    rows = len(re.findall(r"^\|", body, flags=re.M))
    items = len(re.findall(r"^\s*(?:[*-]|\d+\.) ", body, flags=re.M))
    paths = sorted(set(m.replace("docs/it/", "docs/") for m in
                       re.findall(r"`((?:docs|tools|firmware|gateware|hardware|tests|boot|recipes)/[\w./*-]+)`", body)))
    return dict(heads=heads, rows=rows, items=items, fences=fences, paths=paths)


def main():
    en = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "docs", "*.md")))
    it = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "docs", "it", "*.md")))
    errs = []
    if en != it:
        errs.append(f"file sets differ: only EN {sorted(set(en)-set(it))}, only IT {sorted(set(it)-set(en))}")
    pairs = [("README.md", "README.it.md")] + [(f"docs/{n}", f"docs/it/{n}") for n in sorted(set(en) & set(it))]
    for a, b in pairs:
        sa, sb = structure(read(a)), structure(read(b))
        for k in sa:
            if sa[k] != sb[k]:
                errs.append(f"{a} vs {b}: {k} differs: {sa[k] if k != 'paths' else sorted(set(sa[k]) ^ set(sb[k]))} / {sb[k] if k != 'paths' else ''}")
    for e in errs:
        print("DOCS MISMATCH:", e)
    if errs:
        return 1
    print(f"docs check: OK ({len(pairs)} EN/IT pairs in step)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
