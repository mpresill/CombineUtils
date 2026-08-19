#!/usr/bin/env python3
"""Which of the per-parameter impact fits actually produced a usable result.

combineTool.py -M Impacts collects by reading one file per parameter. A single
fit that crashed, hit the wall clock, or converged to nothing leaves a file
that is missing or has too few entries, and the collect step then aborts on the
whole set -- so one bad nuisance out of two hundred costs the entire ranking.

This lists the parameters whose fit is usable, so the collection can be run over
those and the rest reported by name instead.

  --print good     comma separated list of parameters with a usable fit
  --print bad      comma separated list of the others
  --print report   human readable summary
"""
import argparse
import glob
import os
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kFatal

# --algo singles writes the best fit plus the two crossings.
MIN_ENTRIES = 3


def entries(path):
    f = ROOT.TFile.Open(path)
    if not f or f.IsZombie():
        return -1
    t = f.Get("limit")
    return int(t.GetEntries()) if t else -1


def fit_file(directory, name, param):
    pat = os.path.join(directory,
                       "higgsCombine_paramFit_%s_%s.MultiDimFit.mH*.root" % (name, param))
    hits = sorted(glob.glob(pat))
    return hits[-1] if hits else None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=".")
    p.add_argument("--name", required=True, help="the -n tag given to Impacts")
    p.add_argument("--params", required=True, help="comma separated")
    p.add_argument("--initial", help="path to the initial fit, checked too")
    p.add_argument("--print", dest="what", default="good",
                   choices=["good", "bad", "report"])
    p.add_argument("--min-entries", type=int, default=MIN_ENTRIES)
    a = p.parse_args()

    if a.initial:
        n = entries(a.initial)
        if n < a.min_entries:
            sys.stderr.write(
                "the initial fit %s has %d entries (need %d): the POI fit itself "
                "failed, so there is nothing to rank against\n"
                % (os.path.basename(a.initial), n, a.min_entries))
            return 2

    good, bad = [], []
    for param in [x for x in a.params.split(",") if x]:
        path = fit_file(a.dir, a.name, param)
        (good if path and entries(path) >= a.min_entries else bad).append(param)

    if a.what == "good":
        print(",".join(good))
    elif a.what == "bad":
        print(",".join(bad))
    else:
        print("usable per-parameter fits  %d / %d" % (len(good), len(good) + len(bad)))
        if bad:
            print("missing or unusable (%d):" % len(bad))
            for b in bad:
                print("    %s" % b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
