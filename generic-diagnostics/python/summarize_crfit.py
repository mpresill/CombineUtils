#!/usr/bin/env python3
"""Report the rate parameters from a control-region-only fit to data.

`MultiDimFit --algo singles` with N POIs writes 1 + 2N entries in the `limit`
tree: the best fit, then the -1 sigma and +1 sigma points of each POI in turn.
This reads them back, prints each parameter with its uncertainty and how many
sigma it sits from 1, and draws them on one axis.

A rate parameter several sigma from 1 is not automatically a problem -- that is
what it is there for -- but it should be understood, and it should be consistent
between the categories.
"""
import argparse
import sys
import warnings

import numpy as np
import matplotlib

matplotlib.use("Agg")
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt  # noqa: E402
import ROOT  # noqa: E402

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--params", required=True, help="comma separated, fit order")
    p.add_argument("--title", default="")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--report")
    p.add_argument("--reference", type=float, default=1.0)
    a = p.parse_args()

    names = [x for x in a.params.split(",") if x]
    f = ROOT.TFile.Open(a.input)
    t = f.Get("limit") if f else None
    if not t:
        sys.exit("no 'limit' tree in %s" % a.input)

    rows = [[getattr(e, n) for n in names] for e in t]
    if len(rows) < 1 + 2 * len(names):
        sys.exit("expected %d entries for %d parameters, found %d"
                 % (1 + 2 * len(names), len(names), len(rows)))

    best = rows[0]
    out = []
    for i, n in enumerate(names):
        lo, hi = rows[1 + 2 * i][i], rows[2 + 2 * i][i]
        lo, hi = min(lo, hi), max(lo, hi)
        sigma = 0.5 * (hi - lo)
        nsig = (best[i] - a.reference) / sigma if sigma else float("nan")
        out.append(dict(name=n, best=best[i], lo=lo, hi=hi, sigma=sigma, nsig=nsig))

    L = ["title  %s" % a.title,
         "control-region-only fit to observed data (signal regions masked)", "",
         "%-30s %10s %10s %10s %10s" % ("parameter", "value", "-", "+",
                                        "n sigma from %.2f" % a.reference)]
    for r in out:
        L.append("%-30s %10.4f %10.4f %10.4f %10.2f"
                 % (r["name"], r["best"], r["best"] - r["lo"],
                    r["hi"] - r["best"], r["nsig"]))
    far = [r for r in out if abs(r["nsig"]) > 3]
    L.append("")
    if far:
        L.append("!! %d parameter(s) more than 3 sigma from %.2f:"
                 % (len(far), a.reference))
        for r in far:
            L.append("     %-30s %.4f  (%.1f sigma)"
                     % (r["name"], r["best"], r["nsig"]))
        L.append("   Worth understanding before unblinding: it means the")
        L.append("   simulation of that background is off in normalisation.")
    else:
        L.append("every rate parameter is within 3 sigma of %.2f" % a.reference)

    y = np.arange(len(out))
    fig, ax = plt.subplots(figsize=(6.4, max(2.4, 0.55 * len(out) + 1.2)),
                           layout="constrained")
    ax.axvline(a.reference, color="#c0392b", lw=1.3)
    ax.errorbar([r["best"] for r in out], y,
                xerr=[[r["best"] - r["lo"] for r in out],
                      [r["hi"] - r["best"] for r in out]],
                fmt="ko", ms=5, lw=1.3, capsize=3)
    ax.set_yticks(y); ax.set_yticklabels([r["name"] for r in out], fontsize=8.5)
    ax.set_xlabel("fitted value")
    ax.set_title("%s  --  control-region fit to data" % a.title, fontsize=10,
                 loc="left")
    ax.grid(axis="x", ls=":", lw=0.5, alpha=0.6)
    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (a.output_prefix, ext), dpi=140, bbox_inches="tight")
    plt.close(fig)

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
