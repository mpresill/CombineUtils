#!/usr/bin/env python3
"""Collect every CollectGoodnessOfFit json in a directory into one table.

Recomputes the p-value from the toy distribution rather than trusting the value
in the json, and says how many toys actually made it, because a GoF whose toys
mostly failed to converge produces a meaningless p-value that still looks fine.

It also flags the failure mode that these blind cards hit: if the observed test
statistic falls *below* the whole toy distribution, the dataset is not
independent of the model that is being tested -- either the "data" is the
prediction itself, or the model has as many free parameters as there are bins --
and the p-value carries no information at all. That looks like a perfect fit and
is easy to mistake for good news.
"""
import argparse
import glob
import json
import os
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True)
    p.add_argument("--report")
    p.add_argument("--json")
    p.add_argument("--min-toys", type=int, default=50)
    a = p.parse_args()

    files = sorted(glob.glob(os.path.join(a.dir, "gof_*_*.json")))
    files = [f for f in files if "gof_summary" not in os.path.basename(f)]
    vacuous = []
    results = []
    L = ["%-38s %10s %8s %8s %9s" % ("file", "observed", "ntoys", "p-value",
                                     "median toy")]
    if not files:
        L.append("no gof json found in %s" % a.dir)
    for path in files:
        try:
            with open(path) as f:
                d = json.load(f)
        except ValueError:
            L.append("%-38s <not valid json>" % os.path.basename(path))
            continue
        for mass, entry in sorted(d.items()):
            obs = entry.get("obs", [None])
            toys = entry.get("toy", [])
            obs = obs[0] if obs else None
            toys = [t for t in toys if t is not None]
            if obs is None or not toys:
                L.append("%-38s %10s %8d" % (os.path.basename(path), "-", len(toys)))
                continue
            n = len(toys)
            pval = sum(1 for t in toys if t >= obs) / float(n)
            med = sorted(toys)[n // 2]
            note = ""
            if n < a.min_toys:
                note = "  !! only %d toys" % n
            if obs < min(toys):
                note += "  !! VACUOUS: observed below every toy"
                vacuous.append(os.path.basename(path))
            elif pval < 0.01:
                note += "  !! bad fit"
            elif pval > 0.99:
                note += "  !! p-value in the upper tail"
            results.append(dict(name=os.path.basename(path).replace(".json", ""),
                                obs=obs, ntoys=n, pvalue=pval, median_toy=med,
                                vacuous=obs < min(toys)))
            L.append("%-38s %10.2f %8d %8.3f %9.2f%s"
                     % (os.path.basename(path).replace(".json", ""),
                        obs, n, pval, med, note))
    L.append("")
    L.append("A p-value below ~0.05 means the model cannot describe the dataset.")
    if vacuous:
        L.append("")
        L.append("VACUOUS RESULTS -- do not quote these p-values:")
        for v in sorted(set(vacuous)):
            L.append("    %s" % v)
        L.append("")
        L.append("The observed statistic sits below the entire toy distribution,")
        L.append("so the dataset is not independent of the model being tested.")
        L.append("On these cards that is expected while blind:")
        L.append("  * signal regions: data_obs is the MC prediction itself;")
        L.append("  * control regions: one bin each with its own free rate")
        L.append("    parameter, so they are exactly saturated (zero d.o.f.).")
        L.append("Re-run this stage after unblinding, unchanged, for the real")
        L.append("numbers. Until then use the crfit stage for a data check.")

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(results=results, vacuous=sorted(set(vacuous))), f,
                      indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
