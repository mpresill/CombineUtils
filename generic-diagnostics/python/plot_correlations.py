#!/usr/bin/env python3
"""Correlation matrix and POI correlations from a FitDiagnostics output.

Three products:

  <prefix>_poi.png     the parameters most correlated with the POI -- the fast
                       way to see which nuisance actually drives the result and
                       whether a rateParam is degenerate with the signal
  <prefix>.png         the full correlation matrix of the parameters that
                       matter (|rho| above a threshold with anything else)
  <prefix>_report.txt  the same, plus every pair above --pair-warn, which is
                       where degeneracies show up

A pair of nuisances with |rho| close to 1 means the fit cannot tell them apart:
either they are genuinely the same effect entered twice, or one of the two
templates is noise.
"""
import argparse
import re
import sys
import warnings

import numpy as np
import matplotlib

matplotlib.use("Agg")
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
import ROOT  # noqa: E402

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def load(fname, fit="fit_s"):
    f = ROOT.TFile.Open(fname)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % fname)
    fr = f.Get(fit)
    if not fr:
        sys.exit("no %s in %s" % (fit, fname))
    pars = fr.floatParsFinal()
    names = [pars.at(i).GetName() for i in range(pars.getSize())]
    n = len(names)
    rho = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            rho[i, j] = rho[j, i] = fr.correlation(names[i], names[j])
    return names, rho, fr.covQual()


def heatmap(names, rho, path, title):
    n = len(names)
    if n < 2:
        return
    size = max(5.0, 0.26 * n + 2.2)
    fig, ax = plt.subplots(figsize=(size, size), layout="constrained")
    im = ax.imshow(rho, cmap="RdBu_r", norm=TwoSlopeNorm(0.0, -1.0, 1.0))
    ax.set_xticks(range(n)); ax.set_xticklabels(names, rotation=90, fontsize=6)
    ax.set_yticks(range(n)); ax.set_yticklabels(names, fontsize=6)
    ax.set_title(title, fontsize=11, loc="left")
    fig.colorbar(im, ax=ax, fraction=0.03, label=r"$\rho$")
    if n <= 30:
        for i in range(n):
            for j in range(n):
                if abs(rho[i, j]) > 0.25:
                    ax.text(j, i, "%.2f" % rho[i, j], ha="center", va="center",
                            fontsize=5.2,
                            color="white" if abs(rho[i, j]) > 0.6 else "black")
    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (path, ext), dpi=130, bbox_inches="tight")
    plt.close(fig)


def poi_bars(pairs, path, title, poi):
    if not pairs:
        return
    labels = [p[0] for p in pairs][::-1]
    vals = [p[1] for p in pairs][::-1]
    fig, ax = plt.subplots(figsize=(8.5, max(3.0, 0.26 * len(pairs) + 1.2)),
                           layout="constrained")
    colors = ["#c0392b" if v > 0 else "#2471a3" for v in vals]
    ax.barh(range(len(vals)), vals, color=colors, height=0.68)
    ax.set_yticks(range(len(vals))); ax.set_yticklabels(labels, fontsize=7.5)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlim(-1, 1)
    ax.set_xlabel(r"$\rho$ with %s" % poi)
    ax.grid(axis="x", ls=":", lw=0.5, alpha=0.6)
    ax.set_title(title, fontsize=11, loc="left")
    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (path, ext), dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--fit", default="fit_s", choices=["fit_s", "fit_b"])
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--report")
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--matrix-thr", type=float, default=0.20,
                   help="keep a parameter in the matrix if |rho| with some "
                        "other parameter exceeds this")
    p.add_argument("--pair-warn", type=float, default=0.80,
                   help="report pairs above this |rho| as possible degeneracies")
    p.add_argument("--max-matrix", type=int, default=60,
                   help="cap on the matrix size; the most correlated are kept")
    a = p.parse_args()

    names, rho, covqual = load(a.input, a.fit)
    idx = {n: i for i, n in enumerate(names)}

    L = ["input     %s" % a.input,
         "fit       %s" % a.fit,
         "covQual   %d   (3 = accurate and positive definite)" % covqual,
         "params    %d" % len(names), ""]

    # ---- correlations with the POI ---------------------------------------
    pairs = []
    if a.poi in idx:
        i = idx[a.poi]
        pairs = sorted(((n, float(rho[i, j])) for j, n in enumerate(names) if n != a.poi),
                       key=lambda kv: -abs(kv[1]))[:a.top]
        poi_bars(pairs, a.output_prefix + "_poi",
                 "%s  --  correlation with %s" % (a.title, a.poi), a.poi)
        L.append("most correlated with %s" % a.poi)
        for n, v in pairs:
            L.append("    %-44s %+6.3f" % (n, v))
        L.append("")
    else:
        L.append("POI '%s' is not a floating parameter of %s" % (a.poi, a.fit))
        L.append("")

    # ---- degenerate pairs -------------------------------------------------
    off = np.abs(rho - np.eye(len(names)))
    hits = [(names[i], names[j], float(rho[i, j]))
            for i, j in zip(*np.where(np.triu(off, 1) > a.pair_warn))]
    L.append("pairs with |rho| > %.2f  (%d)   <- candidates for a degeneracy"
             % (a.pair_warn, len(hits)))
    for x, y, v in sorted(hits, key=lambda t: -abs(t[2]))[:60]:
        L.append("    %+6.3f   %-38s %s" % (v, x, y))
    L.append("")

    # ---- the matrix itself ------------------------------------------------
    keep = [i for i in range(len(names)) if off[i].max() > a.matrix_thr]
    if a.poi in idx and idx[a.poi] not in keep:
        keep.append(idx[a.poi])
    if len(keep) > a.max_matrix:
        keep = sorted(keep, key=lambda i: -off[i].max())[:a.max_matrix]
    keep = sorted(keep)
    L.append("matrix drawn for %d/%d parameters (|rho| > %.2f with something)"
             % (len(keep), len(names), a.matrix_thr))
    heatmap([names[i] for i in keep], rho[np.ix_(keep, keep)], a.output_prefix,
            "%s  --  correlation matrix (%s)" % (a.title, a.fit))

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
