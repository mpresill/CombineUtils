#!/usr/bin/env python3
"""Write a copy of a datacard whose `shapes` lines point at local file names.

CombineHarvester's ParseDatacard (used by ValidateDatacards.py) prepends the
datacard's directory to the shape file name even when that name is already an
absolute path, so it cannot read a card like these ones. This produces, in
--outdir, a copy of the card with each shape file replaced by its basename plus
a symlink to the real file next to it, which the parser then resolves correctly.

combine itself has no such problem: it is only used for the CH-based checks.
Prints the path of the localized card.
"""
import argparse
import hashlib
import os
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--card", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--name", default="datacard_local.txt")
    p.add_argument("--copy", action="store_true",
                   help="copy the shape files instead of symlinking them")
    a = p.parse_args()

    card_dir = os.path.dirname(os.path.abspath(a.card))
    os.makedirs(a.outdir, exist_ok=True)

    out_lines, linked, taken = [], {}, {}
    with open(a.card) as f:
        for line in f:
            fields = line.split()
            # shapes <process> <channel> <file> [<nominal> <systematic>]
            if len(fields) >= 4 and fields[0] == "shapes":
                src = fields[3]
                if src not in ("FAKE",):
                    abs_src = src if os.path.isabs(src) else os.path.join(card_dir, src)
                    base = os.path.basename(abs_src)
                    # Two `shapes` lines may point at the same file name in
                    # different directories. Using the bare basename would make
                    # the second link overwrite the first and silently validate
                    # the wrong templates, so disambiguate on collision.
                    if base in taken and taken[base] != os.path.realpath(abs_src):
                        stem, ext = os.path.splitext(base)
                        base = "%s_%s%s" % (
                            stem, hashlib.md5(
                                os.path.realpath(abs_src).encode()).hexdigest()[:8], ext)
                    taken[base] = os.path.realpath(abs_src)
                    dest = os.path.join(a.outdir, base)
                    if src not in linked:
                        if not os.path.exists(abs_src):
                            sys.exit("shape file not found: %s" % abs_src)
                        if os.path.lexists(dest):
                            os.remove(dest)
                        if a.copy:
                            shutil.copy2(abs_src, dest)
                        else:
                            os.symlink(os.path.realpath(abs_src), dest)
                        linked[src] = base
                    fields[3] = linked[src]
                    line = "  ".join(fields) + "\n"
            out_lines.append(line)

    out = os.path.join(a.outdir, a.name)
    with open(out, "w") as f:
        f.writelines(out_lines)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
