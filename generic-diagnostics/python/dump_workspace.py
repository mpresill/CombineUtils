#!/usr/bin/env python3
"""Dump and sanity-check the content of a combine workspace.

Prints, and writes to file, the things that are worth a second look before any
fit is trusted:

  * the parameters of interest and their ranges
  * how many constrained nuisances and autoMCStats parameters there are
  * unconstrained parameters (rateParams / flatParams) and their ranges --
    an unbounded rateParam is the single most common cause of a fit that
    wanders off to a nonsense minimum
  * autoMCStats (prop_bin*) parameters, counted per channel
  * parameters sitting exactly on a boundary
  * the observed dataset(s) present in the workspace
"""
import argparse
import json
import re
import sys
from collections import Counter, OrderedDict

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def as_list(argset):
    out = []
    if not argset:
        return out
    it = argset.createIterator()
    a = it.Next()
    while a:
        out.append(a)
        a = it.Next()
    return out


def describe(v):
    d = OrderedDict(name=v.GetName())
    try:
        d["value"] = v.getVal()
        d["min"] = v.getMin()
        d["max"] = v.getMax()
        d["constant"] = bool(v.isConstant())
    except AttributeError:
        d["value"] = None
    return d


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", required=True)
    p.add_argument("--ws-name", default="w")
    p.add_argument("--mc-name", default="ModelConfig")
    p.add_argument("--out-txt")
    p.add_argument("--out-json")
    a = p.parse_args()

    f = ROOT.TFile.Open(a.workspace)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % a.workspace)
    w = f.Get(a.ws_name)
    if not w:
        sys.exit("no RooWorkspace '%s' in %s" % (a.ws_name, a.workspace))
    mc = w.genobj(a.mc_name) or w.obj(a.mc_name)
    if not mc:
        sys.exit("no ModelConfig '%s' in the workspace" % a.mc_name)

    pois = as_list(mc.GetParametersOfInterest())
    nuis = as_list(mc.GetNuisanceParameters())
    globs = as_list(mc.GetGlobalObservables())
    nuis_names = set(v.GetName() for v in nuis)

    mcstat = [v for v in nuis if v.GetName().startswith("prop_bin")]
    mcstat_names = set(v.GetName() for v in mcstat)
    shape_like = [v for v in nuis if v.GetName() not in mcstat_names]

    all_vars = as_list(w.allVars())
    floating = [v for v in all_vars
                if not v.isConstant() and v.GetName() not in nuis_names
                and v.GetName() not in set(x.GetName() for x in pois)
                and not v.GetName().startswith("n_exp")
                and v.GetName() not in set(g.GetName() for g in globs)]
    # rateParams show up here; keep the ones that look like free parameters.
    free = [v for v in floating if hasattr(v, "getMin")
            and v.GetName() not in ("MH", "CMS_th1x")
            and not v.GetName().startswith("shapeBkg")
            and not v.GetName().startswith("shapeSig")]

    boundary = []
    for v in pois + nuis + free:
        try:
            lo, hi, x = v.getMin(), v.getMax(), v.getVal()
        except AttributeError:
            continue
        span = hi - lo
        if span > 0 and (abs(x - lo) < 1e-6 * span or abs(x - hi) < 1e-6 * span):
            boundary.append(v.GetName())

    per_channel = Counter()
    for v in mcstat:
        m = re.match(r"prop_bin(.+)_bin\d+$", v.GetName())
        per_channel[m.group(1) if m else "?"] += 1

    data_names = [d.GetName() for d in w.allData()]

    L = []
    L.append("workspace          %s" % a.workspace)
    L.append("datasets           %s" % (", ".join(data_names) or "<none>"))
    L.append("")
    L.append("parameters of interest (%d)" % len(pois))
    for v in pois:
        L.append("    %-30s = %-10.4g  [%g, %g]"
                 % (v.GetName(), v.getVal(), v.getMin(), v.getMax()))
    L.append("")
    L.append("constrained nuisances     %d" % len(shape_like))
    L.append("autoMCStats parameters    %d" % len(mcstat))
    for ch, n in sorted(per_channel.items()):
        L.append("    %-40s %d" % (ch, n))
    L.append("")
    L.append("free / unconstrained parameters (%d)" % len(free))
    L.append("    these are NOT constrained by any pdf term: check the ranges")
    for v in sorted(free, key=lambda v: v.GetName()):
        try:
            L.append("    %-30s = %-10.4g  [%g, %g]"
                     % (v.GetName(), v.getVal(), v.getMin(), v.getMax()))
        except AttributeError:
            L.append("    %-30s <not a RooRealVar>" % v.GetName())
    L.append("")
    if boundary:
        L.append("!! %d parameter(s) start exactly on a range boundary:" % len(boundary))
        for n in boundary:
            L.append("    %s" % n)
    else:
        L.append("no parameter starts on a range boundary")
    L.append("")
    L.append("nuisance names (first 60):")
    for v in sorted(shape_like, key=lambda v: v.GetName())[:60]:
        L.append("    %s" % v.GetName())
    if len(shape_like) > 60:
        L.append("    ... and %d more" % (len(shape_like) - 60))

    txt = "\n".join(L)
    print(txt)
    if a.out_txt:
        open(a.out_txt, "w").write(txt + "\n")
    if a.out_json:
        json.dump(dict(
            workspace=a.workspace,
            datasets=data_names,
            pois=[describe(v) for v in pois],
            n_constrained=len(shape_like),
            n_mcstat=len(mcstat),
            mcstat_per_channel=dict(per_channel),
            free_parameters=[describe(v) for v in free],
            on_boundary=boundary,
            nuisances=sorted(v.GetName() for v in shape_like),
        ), open(a.out_json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
