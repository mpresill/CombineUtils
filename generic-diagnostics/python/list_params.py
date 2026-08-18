#!/usr/bin/env python3
"""Print the names of workspace parameters matching a regex.

Used by the stages to build combine option strings without hard-coding the
per-category parameter names, which differ between the single-category cards
(`norm_top_boosted_e`) and the combination (`norm_top_boosted_mu`, ...).

    --free        only unconstrained parameters (rateParams, flatParams)
    --nuisances   only the model's nuisance parameters
    --any-of      comma separated union of the categories above, e.g.
                  --any-of nuisances,free
    --sep ','     join with this instead of a newline
"""
import argparse
import re
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def names(argset):
    if not argset:
        return set()
    out = set()
    it = argset.createIterator()
    a = it.Next()
    while a:
        out.add(a.GetName())
        a = it.Next()
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", "-w", required=True)
    p.add_argument("--ws-name", default="w")
    p.add_argument("--mc-name", default="ModelConfig")
    p.add_argument("--regex", default=".*")
    p.add_argument("--free", action="store_true")
    p.add_argument("--nuisances", action="store_true")
    p.add_argument("--any-of", default="",
                   help="comma separated union of 'nuisances' and 'free'")
    p.add_argument("--sep", default="\n")
    a = p.parse_args()

    f = ROOT.TFile.Open(a.workspace)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % a.workspace)
    w = f.Get(a.ws_name)
    if not w:
        sys.exit("no RooWorkspace '%s'" % a.ws_name)
    mc = w.genobj(a.mc_name) or w.obj(a.mc_name)

    nuis = names(mc.GetNuisanceParameters()) if mc else set()
    pois = names(mc.GetParametersOfInterest()) if mc else set()
    globs = names(mc.GetGlobalObservables()) if mc else set()

    def is_free(v, n):
        return not (n in nuis or n in pois or n in globs or v.isConstant()
                    or n.startswith("n_exp") or n.startswith("mask_")
                    or n in ("MH", "CMS_th1x"))

    wanted = set(x for x in a.any_of.split(",") if x)
    rx = re.compile(a.regex)
    out = []
    for v in w.allVars():
        n = v.GetName()
        if not rx.search(n):
            continue
        if wanted:
            if not (("nuisances" in wanted and n in nuis)
                    or ("free" in wanted and is_free(v, n))):
                continue
        else:
            if a.nuisances and n not in nuis:
                continue
            if a.free and not is_free(v, n):
                continue
        out.append(n)
    print(a.sep.join(sorted(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
