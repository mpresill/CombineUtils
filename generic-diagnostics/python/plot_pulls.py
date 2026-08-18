#!/usr/bin/env python3
"""Pull and constraint plot from a FitDiagnostics output.

For every constrained nuisance theta:

    pull       = (theta_postfit - theta_prefit) / sigma_prefit
    constraint = sigma_postfit / sigma_prefit

and the three things worth flagging:

    |pull| > --pull-warn        the dataset wants a different value; on a
                                pre-fit Asimov this can only be a bug
    constraint < --overconstr   the fit shrinks the prior a lot: either the
                                data genuinely constrain it, or the template
                                has a spurious feature the fit is exploiting
    constraint > 1 + eps        the post-fit error is larger than the prior,
                                which usually means a broken/degenerate
                                template or a failed error estimate

Unconstrained parameters (rateParams, flatParams) have no prior to compare to
and are reported separately with their absolute post-fit value.
"""
import argparse
import json
import re
import sys

import warnings

import numpy as np
import matplotlib

warnings.filterwarnings("ignore")

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ROOT  # noqa: E402

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def argset_dict(argset):
    out = {}
    if not argset:
        return out
    it = argset.createIterator()
    a = it.Next()
    while a:
        try:
            out[a.GetName()] = (a.getVal(), a.getError())
        except AttributeError:
            pass
        a = it.Next()
    return out


def result_dict(fitresult):
    out = {}
    if not fitresult:
        return out
    pars = fitresult.floatParsFinal()
    for i in range(pars.getSize()):
        p = pars.at(i)
        out[p.GetName()] = (p.getVal(), p.getError())
    return out


# --------------------------------------------------------------------------- #
def collect(fname, poi):
    f = ROOT.TFile.Open(fname)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % fname)
    prefit = argset_dict(f.Get("nuisances_prefit"))
    fits = {}
    for key, label in (("fit_b", "b-only"), ("fit_s", "s+b")):
        fits[label] = result_dict(f.Get(key))
    if not fits["s+b"]:
        sys.exit("no fit_s in %s" % fname)

    rows, free = [], []
    for name, (post, perr) in sorted(fits["s+b"].items()):
        if name == poi:
            continue
        if name in prefit:
            pre, pre_err = prefit[name]
            if pre_err <= 0:
                free.append(dict(name=name, value=post, error=perr))
                continue
            row = dict(name=name, prefit=pre, prefit_err=pre_err)
            for label in ("b-only", "s+b"):
                v, e = fits[label].get(name, (np.nan, np.nan))
                row["pull_" + label] = (v - pre) / pre_err
                row["constraint_" + label] = e / pre_err
            rows.append(row)
        else:
            b = fits["b-only"].get(name)
            free.append(dict(name=name, value=post, error=perr,
                             value_bonly=b[0] if b else None,
                             error_bonly=b[1] if b else None))
    poi_row = fits["s+b"].get(poi)
    return rows, free, poi_row


# --------------------------------------------------------------------------- #
def draw(rows, path, title, key_pull, key_con, pull_warn, overconstr, inflate):
    if not rows:
        return False
    rows = sorted(rows, key=lambda r: -abs(r[key_pull]))
    n = len(rows)
    h = max(3.0, 0.20 * n + 1.6)
    fig, (axp, axc) = plt.subplots(
        1, 2, figsize=(13, h), sharey=True, layout="constrained",
        gridspec_kw=dict(width_ratios=[2.4, 1.0]))
    y = np.arange(n)[::-1]

    pulls = np.array([r[key_pull] for r in rows])
    cons = np.array([r[key_con] for r in rows])
    names = [r["name"] for r in rows]

    for lo, hi, c in ((-2, 2, "#fff2cc"), (-1, 1, "#d9ead3")):
        axp.axvspan(lo, hi, color=c, zorder=0)
    axp.axvline(0, color="k", lw=0.8, zorder=1)
    colors = ["#c0392b" if abs(p) > pull_warn else "#2c3e50" for p in pulls]
    axp.errorbar(pulls, y, xerr=cons, fmt="o", ms=3.5, lw=1.1,
                 ecolor="#7f8c8d", mfc="none", mec="none", zorder=2)
    axp.scatter(pulls, y, s=16, c=colors, zorder=3)
    axp.set_xlim(-3, 3)
    axp.set_xlabel(r"$(\hat\theta-\theta_0)/\sigma_{\theta_0}$")
    axp.set_yticks(y)
    axp.set_yticklabels(names, fontsize=6.5)
    axp.set_ylim(-1, n)
    axp.grid(axis="x", ls=":", lw=0.5, alpha=0.6)
    axp.set_title("%s  --  pulls" % title, fontsize=10, loc="left")

    ccol = ["#c0392b" if c > inflate else
            ("#e67e22" if c < overconstr else "#2c3e50") for c in cons]
    axc.axvline(1.0, color="k", lw=0.8)
    axc.axvspan(overconstr, inflate, color="#d9ead3", zorder=0)
    axc.barh(y, cons, height=0.6, color=ccol, zorder=2)
    axc.set_xlim(0, max(1.35, float(np.nanmax(cons)) * 1.05))
    axc.set_xlabel(r"$\sigma_{\hat\theta}/\sigma_{\theta_0}$")
    axc.grid(axis="x", ls=":", lw=0.5, alpha=0.6)
    axc.set_title("constraint", fontsize=10, loc="left")

    for ext in ("png", "pdf"):
        fig.savefig("%s.%s" % (path, ext), dpi=140, bbox_inches="tight")
    plt.close(fig)
    return True


# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="fitDiagnostics*.root")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--poi", default="r")
    p.add_argument("--report")
    p.add_argument("--json")
    p.add_argument("--mcstat-regex", default=r"^prop_bin")
    p.add_argument("--pull-warn", type=float, default=1.0)
    p.add_argument("--overconstr", type=float, default=0.5)
    p.add_argument("--inflate", type=float, default=1.05)
    p.add_argument("--expect-zero-pulls", type=int, default=0,
                   help="1 on a pre-fit Asimov: any pull above --zero-tol is a bug")
    p.add_argument("--zero-tol", type=float, default=0.05)
    p.add_argument("--top", type=int, default=40,
                   help="size of the extra 'least ideal parameters' plot")
    a = p.parse_args()

    rows, free, poi_row = collect(a.input, a.poi)
    mcstat_re = re.compile(a.mcstat_regex)
    main_rows = [r for r in rows if not mcstat_re.search(r["name"])]
    mc_rows = [r for r in rows if mcstat_re.search(r["name"])]

    draw(main_rows, a.output_prefix, a.title, "pull_s+b", "constraint_s+b",
         a.pull_warn, a.overconstr, a.inflate)

    # A full plot with 150+ PDF variations is unreadable, so also draw the
    # parameters that are furthest from the ideal (pull 0, constraint 1).
    if len(main_rows) > a.top:
        worst = sorted(main_rows,
                       key=lambda r: -max(abs(r["pull_s+b"]),
                                          abs(1.0 - r["constraint_s+b"])))[:a.top]
        draw(worst, a.output_prefix + "_top", "%s (%d least ideal)" % (a.title, a.top),
             "pull_s+b", "constraint_s+b", a.pull_warn, a.overconstr, a.inflate)
    if mc_rows:
        draw(mc_rows, a.output_prefix + "_mcstat", a.title + " (autoMCStats)",
             "pull_s+b", "constraint_s+b", a.pull_warn, a.overconstr, a.inflate)

    # ---- report ----------------------------------------------------------
    L = ["input   %s" % a.input, "title   %s" % a.title, ""]
    if poi_row:
        L.append("%s = %+.4f +/- %.4f" % (a.poi, poi_row[0], poi_row[1]))
        L.append("")
    if free:
        L.append("unconstrained parameters (no prior -- judge by eye)")
        for r in sorted(free, key=lambda r: r["name"]):
            L.append("    %-32s = %+.4f +/- %.4f" % (r["name"], r["value"], r["error"]))
        L.append("")

    flags = {"large_pull": [], "over_constrained": [], "inflated": [],
             "nonzero_on_asimov": []}
    for r in rows:
        if abs(r["pull_s+b"]) > a.pull_warn:
            flags["large_pull"].append(r)
        if r["constraint_s+b"] < a.overconstr:
            flags["over_constrained"].append(r)
        if r["constraint_s+b"] > a.inflate:
            flags["inflated"].append(r)
        if a.expect_zero_pulls and abs(r["pull_s+b"]) > a.zero_tol:
            flags["nonzero_on_asimov"].append(r)

    def block(title, key, fmt):
        L.append("%s: %d" % (title, len(flags[key])))
        for r in sorted(flags[key], key=lambda r: -abs(r["pull_s+b"]))[:40]:
            L.append("    " + fmt % r)
        L.append("")

    block("|pull| > %.2f" % a.pull_warn, "large_pull",
          "%(name)-38s pull %(pull_s+b)+7.3f   sigma_post/sigma_pre %(constraint_s+b)5.3f")
    block("constraint < %.2f (over-constrained)" % a.overconstr, "over_constrained",
          "%(name)-38s sigma_post/sigma_pre %(constraint_s+b)5.3f  pull %(pull_s+b)+7.3f")
    block("constraint > %.2f (inflated error)" % a.inflate, "inflated",
          "%(name)-38s sigma_post/sigma_pre %(constraint_s+b)5.3f")
    if a.expect_zero_pulls:
        L.append("MODE is a pre-fit Asimov: every pull must be 0 by construction.")
        block("|pull| > %.3f" % a.zero_tol, "nonzero_on_asimov",
              "%(name)-38s pull %(pull_s+b)+7.3f")

    L.append("largest 25 |pull| overall")
    for r in sorted(rows, key=lambda r: -abs(r["pull_s+b"]))[:25]:
        L.append("    %-38s  b-only %+7.3f   s+b %+7.3f   constr %5.3f"
                 % (r["name"], r["pull_b-only"], r["pull_s+b"], r["constraint_s+b"]))
    L.append("")
    L.append("most constrained 25")
    for r in sorted(rows, key=lambda r: r["constraint_s+b"])[:25]:
        L.append("    %-38s  constr %5.3f   pull %+7.3f"
                 % (r["name"], r["constraint_s+b"], r["pull_s+b"]))

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    if a.json:
        json.dump(dict(poi=dict(name=a.poi,
                                value=poi_row[0] if poi_row else None,
                                error=poi_row[1] if poi_row else None),
                       nuisances=rows, free=free,
                       flags={k: [r["name"] for r in v] for k, v in flags.items()}),
                  open(a.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
