#!/usr/bin/env python3
"""Uncertainty breakdown table and plot from a set of MultiDimFit --algo singles runs.

Each --entry LABEL=FILE is one fit. The entry named `total` must be present: it
is the fit with everything floating. For every other group entry, that group was
frozen, so its contribution is

    sigma_group = sqrt(sigma_total^2 - sigma_frozen^2)

Two special labels are understood:
    __stat_only__          everything frozen
    __stat_plus_mcstat__   everything but the MC-statistical parameters frozen

The quadrature sum of the individual group contributions is printed next to the
total systematic component. They will not match exactly -- freezing groups one
at a time double counts the correlations between them -- and how badly they
disagree is itself worth knowing.
"""
import argparse
import json
import math
import os
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


def read_singles(path, poi, rmin=None, rmax=None):
    """--algo singles writes 3 entries: best fit, then the -1s and +1s points.

    When the minimiser fails to find a crossing it reports the distance to the
    edge of the parameter range instead, which looks like a huge but valid
    uncertainty. Those results are rejected here rather than propagated into the
    table.
    """
    f = ROOT.TFile.Open(path)
    t = f.Get("limit") if f else None
    if not t:
        return None
    vals = [getattr(e, poi) for e in t]
    if len(vals) < 3:
        return None
    best, lo, hi = vals[0], min(vals[1:3]), max(vals[1:3])
    tol = 1e-3
    for edge in (rmin, rmax):
        if edge is None:
            continue
        if abs(lo - edge) < tol or abs(hi - edge) < tol:
            print("  !! %s: the %s error ran into the range edge (%g) -- "
                  "the fit did not converge, dropping this point"
                  % (os.path.basename(path), poi, edge))
            return None
    return dict(best=best, lo=lo, hi=hi,
                down=best - lo, up=hi - best, sigma=0.5 * (hi - lo))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entry", action="append", default=[], metavar="LABEL=FILE")
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--report")
    p.add_argument("--json")
    p.add_argument("--rmin", type=float, help="fit range, to detect "
                                              "uncertainties that ran into it")
    p.add_argument("--rmax", type=float)
    a = p.parse_args()

    fits = {}
    for spec in a.entry:
        label, _, path = spec.partition("=")
        r = read_singles(path, a.poi, a.rmin, a.rmax)
        if r is None:
            print("could not read %s (%s)" % (label, path))
            continue
        fits[label] = r

    if "total" not in fits:
        sys.exit("no 'total' entry -- cannot compute a breakdown")
    tot = fits["total"]

    stat = fits.get("__stat_only__")
    statmc = fits.get("__stat_plus_mcstat__")

    rows = []
    for label, r in fits.items():
        if label.startswith("__") or label == "total":
            continue
        d = tot["sigma"] ** 2 - r["sigma"] ** 2
        rows.append(dict(group=label, sigma_frozen=r["sigma"],
                         contribution=math.sqrt(d) if d > 0 else -math.sqrt(-d),
                         best=r["best"]))
    rows.sort(key=lambda x: -abs(x["contribution"]))

    L = ["title  %s" % a.title, ""]
    L.append("%s = %+.4f  +%.4f / -%.4f     (total, everything floating)"
             % (a.poi, tot["best"], tot["up"], tot["down"]))
    L.append("total sigma            %.4f" % tot["sigma"])
    syst_total = None
    if stat:
        L.append("statistical only       %.4f  (%s = %+.4f)"
                 % (stat["sigma"], a.poi, stat["best"]))
        d = tot["sigma"] ** 2 - stat["sigma"] ** 2
        syst_total = math.sqrt(d) if d > 0 else float("nan")
        L.append("systematic (quadr.)    %.4f" % syst_total)
    if statmc:
        d = statmc["sigma"] ** 2 - (stat["sigma"] ** 2 if stat else 0.0)
        L.append("MC statistical         %.4f"
                 % (math.sqrt(d) if d > 0 else float("nan")))
    L.append("")
    L.append("%-18s %12s %14s %10s" % ("group", "sigma frozen", "contribution",
                                       "% of tot"))
    for r in rows:
        L.append("%-18s %12.4f %14.4f %9.1f%%"
                 % (r["group"], r["sigma_frozen"], r["contribution"],
                    100 * abs(r["contribution"]) / tot["sigma"] if tot["sigma"] else 0))
    qsum = math.sqrt(sum(r["contribution"] ** 2 for r in rows
                         if r["contribution"] > 0))
    L.append("")
    L.append("quadrature sum of the groups   %.4f" % qsum)
    if syst_total is not None and syst_total == syst_total:
        L.append("systematic from stat-only fit  %.4f" % syst_total)
        L.append("(a large difference means the groups are correlated with each "
                 "other; the stat-only number is the one to quote)")
    if any(r["contribution"] < 0 for r in rows):
        L.append("")
        L.append("!! a negative contribution means the frozen fit came out WIDER")
        L.append("   than the total fit, which cannot happen physically: those")
        L.append("   fits did not converge to the same minimum. Check their logs.")

    # ---- plot -------------------------------------------------------------
    if rows:
        labels = [r["group"] for r in rows][::-1]
        vals = [r["contribution"] for r in rows][::-1]
        fig, ax = plt.subplots(figsize=(7.2, max(3.0, 0.4 * len(rows) + 1.6)),
                               layout="constrained")
        colors = ["#c0392b" if v < 0 else "#2471a3" for v in vals]
        ax.barh(range(len(vals)), vals, color=colors, height=0.66)
        ax.set_yticks(range(len(vals)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.axvline(tot["sigma"], color="k", ls="--", lw=1.0,
                   label="total  %.3f" % tot["sigma"])
        if stat:
            ax.axvline(stat["sigma"], color="#2c3e50", ls=":", lw=1.0,
                       label="stat only  %.3f" % stat["sigma"])
        ax.set_xlabel(r"contribution to $\sigma_{%s}$" % a.poi)
        ax.set_title("%s  --  uncertainty breakdown" % a.title, fontsize=10,
                     loc="left")
        ax.legend(fontsize=8, frameon=False)
        ax.grid(axis="x", ls=":", lw=0.5, alpha=0.6)
        for ext in ("png", "pdf"):
            fig.savefig("%s.%s" % (a.output_prefix, ext), dpi=140,
                        bbox_inches="tight")
        plt.close(fig)

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    if a.json:
        json.dump(dict(poi=a.poi, total=tot, stat_only=stat,
                       stat_plus_mcstat=statmc, groups=rows,
                       quadrature_sum=qsum, systematic=syst_total),
                  open(a.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
