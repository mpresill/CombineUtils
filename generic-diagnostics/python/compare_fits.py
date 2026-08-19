#!/usr/bin/env python3
"""Compare the POI from several MultiDimFit --algo singles runs.

Used to check that the answer does not depend on the minimiser configuration. A
spread in the central value above --tol-value, or in the uncertainty above
--tol-error, means the likelihood is hard to minimise and every downstream
number (impacts, breakdown, significance) inherits that instability.
"""
import argparse
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def read(path, poi):
    if not path:
        return None
    f = ROOT.TFile.Open(path)
    t = f.Get("limit") if f else None
    if not t:
        return None
    vals = [getattr(e, poi) for e in t]
    if len(vals) < 3:
        return None
    best, lo, hi = vals[0], min(vals[1:3]), max(vals[1:3])
    return dict(best=best, down=best - lo, up=hi - best, sigma=0.5 * (hi - lo))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entry", action="append", default=[], metavar="LABEL=FILE")
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--report")
    p.add_argument("--tol-value", type=float, default=0.01)
    p.add_argument("--tol-error", type=float, default=0.05)
    a = p.parse_args()

    rows = []
    for spec in a.entry:
        label, _, path = spec.partition("=")
        r = read(path, a.poi)
        if r is None:
            rows.append((label, None))
            continue
        rows.append((label, r))

    L = ["title  %s" % a.title, "",
         "%-26s %10s %10s %10s" % ("configuration", a.poi, "+", "-")]
    good = [r for _, r in rows if r]
    for label, r in rows:
        if r is None:
            L.append("%-26s %10s" % (label, "<failed>"))
        else:
            L.append("%-26s %10.4f %10.4f %10.4f"
                     % (label, r["best"], r["up"], r["down"]))
    L.append("")
    if len(good) >= 2:
        vals = [r["best"] for r in good]
        sig = [r["sigma"] for r in good]
        dv = max(vals) - min(vals)
        ds = (max(sig) - min(sig)) / max(sig) if max(sig) else 0.0
        L.append("spread in %s        %.5f  (tolerance %.3f)" % (a.poi, dv, a.tol_value))
        L.append("relative spread in sigma  %.3f  (tolerance %.3f)" % (ds, a.tol_error))
        if dv > a.tol_value or ds > a.tol_error:
            L.append("")
            L.append("!! the result depends on the minimiser configuration.")
            L.append("   Do not trust the impacts or the breakdown until this is")
            L.append("   understood; usually a rateParam hitting a bound or a")
            L.append("   template with a discontinuity (see the FastScan output).")
        else:
            L.append("the fit is stable against the minimiser configuration")
    else:
        L.append("fewer than two successful fits -- nothing to compare")

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
