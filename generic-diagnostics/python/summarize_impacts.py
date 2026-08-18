#!/usr/bin/env python3
"""Rank and flag the nuisances in a combineTool Impacts json.

Beyond the ranking that plotImpacts.py draws, this points at the combinations
that indicate a problem rather than physics:

  * a large impact together with a large pull -- the parameter is not being
    constrained, it is being used to absorb a mismodelling
  * a large impact together with a heavily shrunk post-fit error -- the fit is
    exploiting a feature of that template
  * an asymmetric impact (|up| and |down| very different) -- a sign that the
    likelihood is not parabolic in that direction
"""
import argparse
import json
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--poi", default="r")
    p.add_argument("--title", default="")
    p.add_argument("--report")
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--pull-warn", type=float, default=1.0)
    p.add_argument("--constraint-warn", type=float, default=0.5)
    p.add_argument("--asym-warn", type=float, default=2.0)
    a = p.parse_args()

    with open(a.input) as f:
        d = json.load(f)
    params = d.get("params", [])
    if not params:
        sys.exit("no 'params' in %s" % a.input)

    poi_fit = d.get("POIs", [{}])[0].get("fit", [None, None, None])

    # json layout per parameter:
    #   fit      [-1sigma, best, +1sigma] of the nuisance itself
    #   prefit   the same before the fit (all equal for unconstrained ones)
    #   <poi>    [lo, best, hi] of the POI when the nuisance is moved +-1sigma
    #   type     Gaussian / Poisson / Unconstrained
    rows = []
    for e in params:
        imp = e.get("impact_" + a.poi)
        if imp is None:
            continue
        lo, mid, hi = e.get("fit", [0, 0, 0])
        pre = e.get("prefit") or [-1, 0, 1]
        unconstrained = e.get("type") == "Unconstrained"
        sigma_pre = 0.5 * (pre[2] - pre[0])
        sigma_post = 0.5 * (hi - lo)
        poi_shift = e.get(a.poi) or [0, 0, 0]
        rows.append(dict(
            name=e["name"], impact=abs(imp), type=e.get("type", "?"),
            up=poi_shift[2] - poi_shift[1], down=poi_shift[0] - poi_shift[1],
            value=mid, sigma=sigma_post,
            pull=(mid - pre[1]) / sigma_pre if sigma_pre > 0 else float("nan"),
            constraint=(sigma_post / sigma_pre) if sigma_pre > 0 and not unconstrained
            else float("nan")))
    rows.sort(key=lambda r: -r["impact"])

    L = ["title  %s" % a.title, "input  %s" % a.input, ""]
    if poi_fit and poi_fit[1] is not None:
        L.append("%s = %+.4f  +%.4f / -%.4f"
                 % (a.poi, poi_fit[1], poi_fit[2] - poi_fit[1], poi_fit[1] - poi_fit[0]))
        L.append("")
    def f(v, spec="%8.3f"):
        return (spec % v) if v == v else "       -"
    L.append("%-44s %9s %9s %9s %8s %8s  %s"
             % ("parameter", "impact", "d" + a.poi + "+", "d" + a.poi + "-",
                "pull", "constr", "type"))
    for r in rows[:a.top]:
        L.append("%-44s %9.4f %+9.4f %+9.4f %s %s  %s"
                 % (r["name"], r["impact"], r["up"], r["down"],
                    f(r["pull"]), f(r["constraint"]), r["type"]))
    L.append("")

    def flag(title, pred):
        hits = [r for r in rows if pred(r)]
        L.append("%s: %d" % (title, len(hits)))
        for r in sorted(hits, key=lambda r: -r["impact"])[:20]:
            L.append("    %-44s impact %7.4f  pull %s  constr %s"
                     % (r["name"], r["impact"], f(r["pull"], "%+6.3f"),
                        f(r["constraint"], "%5.3f")))
        L.append("")

    top_imp = rows[0]["impact"] if rows else 0.0
    def big(r):
        return r["impact"] > 0.2 * top_imp
    flag("large impact AND |pull| > %.2f" % a.pull_warn,
         lambda r: r["pull"] == r["pull"] and abs(r["pull"]) > a.pull_warn and big(r))
    flag("large impact AND constraint < %.2f" % a.constraint_warn,
         lambda r: r["constraint"] == r["constraint"]
         and r["constraint"] < a.constraint_warn and big(r))
    flag("strongly asymmetric impact (ratio > %.1f)" % a.asym_warn,
         lambda r: min(abs(r["up"]), abs(r["down"])) > 1e-6
         and max(abs(r["up"]), abs(r["down"])) / min(abs(r["up"]), abs(r["down"]))
         > a.asym_warn and big(r))

    txt = "\n".join(L)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
