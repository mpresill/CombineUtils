#!/usr/bin/env python3
"""Pre-fit and post-fit distributions from a FitDiagnostics output.

Needs a FitDiagnostics run with --saveShapes --saveWithUncertainties, which
stores, per channel, every process plus `total`, `total_background`,
`total_signal` and the dataset that was fitted, in the directories

    shapes_prefit / shapes_fit_b / shapes_fit_s

For each channel and each of those three, one plot is produced: stacked
backgrounds, the signal overlaid, the fitted dataset as points, and a ratio
panel with the uncertainty band of the total prediction.

While the analysis is blind the "data" points are the Asimov dataset, not real
data, so these plots are a check of the model and of the fit, not of agreement
with observation. The exception is the control regions, whose data_obs is real.
"""
import argparse
import json
import os
import re
import sys
import warnings

import numpy as np
import matplotlib

matplotlib.use("Agg")
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import ROOT  # noqa: E402

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError

FITS = [("shapes_prefit", "pre-fit"),
        ("shapes_fit_b", "post-fit (b-only)"),
        ("shapes_fit_s", "post-fit (s+b)")]

FALLBACK_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
                   "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"]


def th1_arrays(h):
    n = h.GetNbinsX()
    e = np.array([h.GetBinLowEdge(i) for i in range(1, n + 2)])
    v = np.array([h.GetBinContent(i) for i in range(1, n + 1)])
    err = np.array([h.GetBinError(i) for i in range(1, n + 1)])
    return e, v, err


def graph_arrays(g):
    n = g.GetN()
    x = np.array([g.GetPointX(i) for i in range(n)])
    y = np.array([g.GetPointY(i) for i in range(n)])
    lo = np.array([g.GetErrorYlow(i) for i in range(n)])
    hi = np.array([g.GetErrorYhigh(i) for i in range(n)])
    return x, y, lo, hi


def load_groups(path):
    if not path:
        return None
    with open(path) as f:
        return json.load(f)["groups"]


def assign(procs, groups):
    """-> [(label, color, is_signal, [processes])] in stacking order."""
    if not groups:
        return [(p, FALLBACK_COLORS[i % len(FALLBACK_COLORS)], False, [p])
                for i, p in enumerate(sorted(procs))]
    out, taken = [], set()
    for i, g in enumerate(groups):
        rx = re.compile(g["regex"])
        members = sorted(p for p in procs if rx.search(p) and p not in taken)
        taken.update(members)
        if members:
            out.append((g["label"], g.get("color", FALLBACK_COLORS[i % 10]),
                        bool(g.get("signal")), members))
    left = sorted(p for p in procs if p not in taken)
    if left:
        out.insert(0, ("other", "#bab0ac", False, left))
    return out


def channel_plot(fdir, chan, groups, label, outpath, title, logy):
    d = fdir.Get(chan)
    if not d:
        return None
    procs = [k.GetName() for k in d.GetListOfKeys()
             if k.GetClassName().startswith("TH1")
             and k.GetName() not in ("total", "total_signal", "total_background",
                                     "total_covar")]
    total = d.Get("total")
    if not total:
        return None
    edges, tot, tot_err = th1_arrays(total)
    # combine writes every channel over the same CMS_th1x range, so a channel
    # with fewer bins than the widest one is zero padded. Trim that padding.
    filled = np.nonzero(tot > 0)[0]
    if len(filled) == 0:
        return None
    lo, hi = filled[0], filled[-1] + 1
    keep = slice(lo, hi)
    edges = edges[lo:hi + 1]
    tot, tot_err = tot[keep], tot_err[keep]
    centres = 0.5 * (edges[1:] + edges[:-1])
    widths = np.diff(edges)

    stack, sig = [], []
    for lab, color, is_sig, members in assign(procs, groups):
        acc = None
        for m in members:
            h = d.Get(m)
            if not h:
                continue
            _, v, _ = th1_arrays(h)
            v = v[keep]
            acc = v if acc is None else acc + v
        if acc is None or not np.any(acc):
            continue
        (sig if is_sig else stack).append((lab, color, acc))

    fig, (ax, rax) = plt.subplots(
        2, 1, figsize=(6.6, 5.6), sharex=True, layout="constrained",
        gridspec_kw=dict(height_ratios=[3, 1]))

    bottom = np.zeros_like(tot)
    for lab, color, v in stack:
        ax.bar(centres, v, width=widths, bottom=bottom, color=color,
               edgecolor="white", lw=0.3, label=lab)
        bottom = bottom + v
    for lab, color, v in sig:
        ax.stairs(v, edges, color=color, lw=1.9, baseline=None,
                  label="%s (%.3g ev)" % (lab, v.sum()))

    ax.bar(centres, 2 * tot_err, width=widths, bottom=tot - tot_err,
           facecolor="none", edgecolor="#2c3e50", hatch="/////", lw=0.0,
           label="total unc.")

    gdata = d.Get("data")
    dy = None
    if gdata:
        dx, dy, dlo, dhi = graph_arrays(gdata)
        m = (dx >= edges[0]) & (dx <= edges[-1])
        dx, dy, dlo, dhi = dx[m], dy[m], dlo[m], dhi[m]
        ax.errorbar(dx, dy, yerr=[dlo, dhi], fmt="ko", ms=3.5, lw=1.0,
                    label="dataset fitted")

    ax.set_ylabel("events / bin")
    if logy:
        ax.set_yscale("log")
        ax.set_ylim(max(1e-3, 0.5 * min(v for v in tot if v > 0)), 60 * tot.max())
    else:
        ax.set_ylim(0, 1.55 * max(tot.max(), (dy.max() if dy is not None else 0)))
    ax.set_title("%s   %s   [%s]" % (title, chan, label), fontsize=9, loc="left")
    ax.legend(fontsize=6.5, ncol=3, frameon=False, loc="upper right")

    safe = np.where(tot > 0, tot, np.nan)
    rax.fill_between(edges, np.append(1 - tot_err / safe, np.nan),
                     np.append(1 + tot_err / safe, np.nan), step="post",
                     color="#2c3e50", alpha=0.22, lw=0)
    rax.axhline(1.0, color="k", lw=0.8)
    if dy is not None:
        rax.errorbar(dx, dy / safe, yerr=[dlo / safe, dhi / safe],
                     fmt="ko", ms=3.5, lw=1.0)
    rax.set_ylim(0.5, 1.5)
    rax.set_ylabel("data / pred.", fontsize=8)
    rax.set_xlabel("discriminant bin")
    rax.grid(axis="y", ls=":", lw=0.5, alpha=0.6)

    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (outpath, ext), dpi=140, bbox_inches="tight")
    plt.close(fig)

    chi2 = np.nansum(((dy - tot) / np.sqrt(np.where(tot > 0, tot, np.nan))) ** 2) \
        if dy is not None else float("nan")
    return dict(channel=chan, fit=label, total=float(tot.sum()),
                data=float(dy.sum()) if dy is not None else None,
                nbins=int(len(tot)), chi2_poisson=float(chi2))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="fitDiagnostics*.root")
    p.add_argument("--outdir", required=True)
    p.add_argument("--groups-json")
    p.add_argument("--title", default="")
    p.add_argument("--prefix", default="shapes")
    p.add_argument("--logy", action="store_true")
    p.add_argument("--report")
    a = p.parse_args()

    f = ROOT.TFile.Open(a.input)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % a.input)
    groups = load_groups(a.groups_json)
    os.makedirs(a.outdir, exist_ok=True)

    rows, made = [], 0
    for key, label in FITS:
        fdir = f.Get(key)
        if not fdir:
            print("no %s in the file (was --saveShapes used?)" % key)
            continue
        chans = [k.GetName() for k in fdir.GetListOfKeys()
                 if k.GetClassName() == "TDirectoryFile"]
        for chan in sorted(chans):
            tag = key.replace("shapes_", "")
            out = os.path.join(a.outdir, "%s_%s_%s" % (a.prefix, chan, tag))
            r = channel_plot(fdir, chan, groups, label, out, a.title, a.logy)
            if r:
                rows.append(r)
                made += 1

    L = ["input %s" % a.input, "%d plots written to %s" % (made, a.outdir), "",
         "%-26s %-20s %10s %10s %8s %8s" % ("channel", "fit", "prediction",
                                            "dataset", "nbins", "chi2/n")]
    for r in rows:
        L.append("%-26s %-20s %10.2f %10s %8d %8s"
                 % (r["channel"], r["fit"], r["total"],
                    "%.2f" % r["data"] if r["data"] is not None else "-",
                    r["nbins"],
                    "%.2f" % (r["chi2_poisson"] / r["nbins"])
                    if r["chi2_poisson"] == r["chi2_poisson"] else "-"))
    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
