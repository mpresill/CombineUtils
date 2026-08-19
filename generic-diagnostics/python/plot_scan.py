#!/usr/bin/env python3
"""Profile-likelihood scan plot and the intervals that go with it.

Reads one or more `limit` trees written by `combine -M MultiDimFit --algo grid`
and draws 2*deltaNLL against the POI, with the 68% and 95% crossings marked.

Reports:
  * the best fit and the 68%/95% intervals, obtained by interpolating the
    crossings rather than by trusting the minimiser's parabolic error
  * the systematic component, sqrt(sigma_total^2 - sigma_stat^2), when a
    stat-only scan is supplied
  * whether the curve is well behaved: monotonic on each side of the minimum,
    minimum not at the edge of the scanned range, no negative deltaNLL
"""
import argparse
import json
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


def read_scan(path, poi):
    f = ROOT.TFile.Open(path)
    t = f.Get("limit") if f else None
    if not t:
        sys.exit("no 'limit' tree in %s" % path)
    x, y = [], []
    for e in t:
        x.append(getattr(e, poi))
        y.append(2.0 * e.deltaNLL)
    x = np.array(x)
    y = np.array(y)
    o = np.argsort(x)
    x, y = x[o], y[o]
    # combine references deltaNLL to the nominal fit, so a grid point that found
    # a better minimum shows up as a *negative* value. Record that before
    # shifting the curve to zero, otherwise the health check below can never
    # see it.
    below = float(y.min())
    keep = np.concatenate(([True], np.diff(x) > 0))
    y = y - y.min()
    return x[keep], y[keep], below


def crossings(x, y, level):
    """Interpolated x where y crosses `level`, split around the minimum."""
    i0 = int(np.argmin(y))
    out = [None, None]
    for side, rng in ((0, range(i0, 0, -1)), (1, range(i0, len(x) - 1))):
        for i in rng:
            j = i - 1 if side == 0 else i + 1
            if (y[i] - level) * (y[j] - level) <= 0 and y[j] != y[i]:
                out[side] = x[i] + (level - y[i]) * (x[j] - x[i]) / (y[j] - y[i])
                break
    return out


def interval(x, y, level):
    lo, hi = crossings(x, y, level)
    best = x[int(np.argmin(y))]
    return best, lo, hi


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--main", required=True, help="total (all nuisances profiled)")
    p.add_argument("--stat", help="stat-only scan")
    p.add_argument("--extra", nargs="*", default=[],
                   metavar="FILE:LABEL", help="further curves to overlay")
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--report")
    p.add_argument("--y-max", type=float, default=9.0)
    a = p.parse_args()

    curves = [("total", "#c0392b") + read_scan(a.main, a.poi)]
    if a.stat:
        curves.append(("stat only", "#2471a3") + read_scan(a.stat, a.poi))
    for i, spec in enumerate(a.extra):
        path, _, label = spec.partition(":")
        curves.append((label or "extra%d" % i, "#7f8c8d") + read_scan(path, a.poi))

    fig, ax = plt.subplots(figsize=(6.4, 4.6), layout="constrained")
    for lvl, lab in ((1.0, "68%"), (3.84, "95%")):
        ax.axhline(lvl, color="#7f8c8d", ls="--", lw=0.8)
        ax.text(ax.get_xlim()[0], lvl, " " + lab, va="bottom", ha="left",
                fontsize=7, color="#7f8c8d")

    L = ["title  %s" % a.title, ""]
    out = {}
    for label, color, x, y, below in curves:
        ax.plot(x, y, color=color, lw=1.8, label=label)
        best, lo68, hi68 = interval(x, y, 1.0)
        _, lo95, hi95 = interval(x, y, 3.84)
        sig = None
        if lo68 is not None and hi68 is not None:
            sig = 0.5 * (hi68 - lo68)
        out[label] = dict(best=float(best),
                          lo68=lo68, hi68=hi68, lo95=lo95, hi95=hi95,
                          sigma=sig)
        L.append("%s" % label)
        L.append("    best fit   %s = %+.4f" % (a.poi, best))
        L.append("    68%%        [%s, %s]" % (
            "%+.4f" % lo68 if lo68 is not None else "  --  ",
            "%+.4f" % hi68 if hi68 is not None else "  --  "))
        L.append("    95%%        [%s, %s]" % (
            "%+.4f" % lo95 if lo95 is not None else "  --  ",
            "%+.4f" % hi95 if hi95 is not None else "  --  "))
        # health of the curve
        i0 = int(np.argmin(y))
        notes = []
        if i0 in (0, len(x) - 1):
            notes.append("minimum sits at the edge of the scanned range")
        if below < -1e-6:
            notes.append("negative 2*deltaNLL (%.3g): a grid point found a "
                         "better minimum than the nominal fit" % below)
        left, right = y[:i0 + 1][::-1], y[i0:]
        if np.any(np.diff(left) < -1e-3) or np.any(np.diff(right) < -1e-3):
            notes.append("curve is not monotonic away from the minimum: "
                         "minimiser instability")
        if lo68 is None or hi68 is None:
            notes.append("the 68%% crossing is outside the scanned range")
        for n in notes:
            L.append("    !! %s" % n)
        out[label]["notes"] = notes
        L.append("")

    if a.stat and out.get("total", {}).get("sigma") and out.get("stat only", {}).get("sigma"):
        st, ss = out["total"]["sigma"], out["stat only"]["sigma"]
        syst = (st ** 2 - ss ** 2) ** 0.5 if st > ss else float("nan")
        L.append("uncertainty breakdown from the two scans")
        L.append("    total        %.4f" % st)
        L.append("    statistical  %.4f" % ss)
        L.append("    systematic   %.4f" % syst)
        out["breakdown"] = dict(total=st, stat=ss, syst=syst)
        L.append("")

    ax.set_ylim(0, a.y_max)
    ax.set_xlabel(a.poi)
    ax.set_ylabel(r"$-2\,\Delta\ln L$")
    ax.set_title(a.title, fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(ls=":", lw=0.5, alpha=0.6)
    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (a.output_prefix, ext), dpi=140, bbox_inches="tight")
    plt.close(fig)

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
        json.dump(out, open(a.report.rsplit(".", 1)[0] + ".json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
