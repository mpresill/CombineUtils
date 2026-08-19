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


# Anything below this is "numerically zero" for a GoF statistic.
ZERO = 1e-6


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
            srt = sorted(toys)
            med = srt[n // 2]
            spread = srt[-1] - srt[0]

            # Is the test degenerate rather than merely lopsided?
            #
            # Ranking alone does not answer this: with a perfectly good model
            # the observed statistic lands below every toy with probability
            # 1/(n+1), so "below the minimum" on its own is not evidence of
            # saturation. What is evidence is a statistic that is *numerically*
            # zero, or a toy distribution with no width -- both mean the model
            # has no degrees of freedom left to test against this dataset.
            why = []
            if abs(obs) < ZERO:
                why.append("the observed statistic is 0")
            if spread < ZERO:
                why.append("every toy gives the same statistic")
            if med > ZERO and abs(obs) < 1e-3 * med:
                why.append("the observed statistic is %.1e, "
                           "%.0fx below the toy median" % (obs, med / max(obs, 1e-12)))
            is_vac = bool(why)

            note = ""
            if n < a.min_toys:
                note = "  !! only %d toys" % n
            if is_vac:
                note += "  !! VACUOUS: " + "; ".join(why)
                vacuous.append(os.path.basename(path))
            elif obs < min(toys):
                note += ("  !! observed below all %d toys -- suspicious, but "
                         "expected in 1/%d of good fits" % (n, n + 1))
            elif pval < 0.01:
                note += "  !! bad fit"
            elif pval > 0.99:
                note += "  !! p-value in the upper tail"
            results.append(dict(name=os.path.basename(path).replace(".json", ""),
                                obs=obs, ntoys=n, pvalue=pval, median_toy=med,
                                toy_spread=spread,
                                vacuous=is_vac, vacuous_why=why))
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
        L.append("The test statistic is degenerate -- identically zero, or with")
        L.append("a toy distribution of no width -- so the model has no degrees")
        L.append("of freedom left to test against this dataset.")
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
