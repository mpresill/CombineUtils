#!/usr/bin/env python3
"""Per-channel signal strengths from ChannelCompatibilityCheck.

Draws the combined value as a band and each channel group as a point, and
reports the compatibility p-value that combine printed as well as the largest
deviation of any group from the combined value.

On an Asimov dataset every group must sit on the injected value: a group that
does not means its templates are inconsistent with the rest of the combination.
"""
import argparse
import math
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
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--report")
    a = p.parse_args()

    f = ROOT.TFile.Open(a.input)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % a.input)

    nominal = f.Get("fit_nominal")
    alt = f.Get("fit_alternate")
    if not nominal or not alt:
        sys.exit("no fit_nominal/fit_alternate: was --saveFitResult used?")

    comb = nominal.floatParsFinal().find(a.poi)
    comb_val = comb.getVal() if comb else float("nan")
    comb_err = comb.getError() if comb else float("nan")

    # combine names them _ChannelCompatibilityCheck_<poi>_<group>
    prefix = "_ChannelCompatibilityCheck_%s_" % a.poi
    pars = alt.floatParsFinal()
    rows = []
    for i in range(pars.getSize()):
        v = pars.at(i)
        if not v.GetName().startswith(prefix):
            continue
        rows.append((v.GetName()[len(prefix):], v.getVal(),
                     v.getErrorLo(), v.getErrorHi()))
    rows.sort()
    if not rows:
        sys.exit("no _ChannelCompatibilityCheck_%s_* parameters in the fit result"
                 % a.poi)

    # 2 * deltaNLL between the one-r and the many-r fits
    ndof = max(0, len(rows) - 1)
    q = 2.0 * (nominal.minNll() - alt.minNll())
    pval = ROOT.TMath.Prob(q, ndof) if ndof > 0 and q > 0 else float("nan")

    L = ["title  %s" % a.title, "",
         "combined            %s = %+.4f +/- %.4f" % (a.poi, comb_val, comb_err),
         "channel groups      %d" % len(rows),
         "2*dNLL (1 r vs %d r) = %.4f,  ndof = %d,  p-value = %.3f"
         % (len(rows), q, ndof, pval), "",
         "%-22s %10s %10s %10s %8s" % ("group", a.poi, "-", "+", "n sigma")]
    worst = (None, 0.0)
    for label, v, lo, hi in rows:
        err = abs(lo) if v < comb_val else abs(hi)
        tot = math.sqrt(err ** 2 + comb_err ** 2) if err else float("nan")
        nsig = (v - comb_val) / tot if tot and tot == tot else float("nan")
        L.append("%-22s %10.4f %10.4f %10.4f %8.2f" % (label, v, lo, hi, nsig))
        if abs(nsig) > abs(worst[1]):
            worst = (label, nsig)
    L.append("")
    if worst[0]:
        L.append("largest deviation from the combined value: %s at %.2f sigma"
                 % (worst[0], worst[1]))
    if pval == pval and pval < 0.05:
        L.append("!! the channel groups are not statistically compatible "
                 "(p = %.3f)" % pval)

    if rows:
        y = np.arange(len(rows))
        fig, ax = plt.subplots(figsize=(6.6, max(2.6, 0.5 * len(rows) + 1.4)),
                               layout="constrained")
        ax.axvspan(comb_val - comb_err, comb_val + comb_err, color="#f5b7b1",
                   alpha=0.6, label="combined  %.3f $\\pm$ %.3f" % (comb_val, comb_err))
        ax.axvline(comb_val, color="#c0392b", lw=1.4)
        ax.errorbar([r[1] for r in rows], y,
                    xerr=[[abs(r[2]) for r in rows], [abs(r[3]) for r in rows]],
                    fmt="ko", ms=5, lw=1.3, capsize=3)
        ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=9)
        ax.set_xlabel(a.poi)
        ax.set_title("%s  --  channel compatibility (p = %.3f)" % (a.title, pval),
                     fontsize=10, loc="left")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
