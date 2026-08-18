#!/usr/bin/env python3
"""List the channels of a combine workspace, and the mask_* parameters that
text2workspace.py --channel-masks created for them.

    --list-channels        one channel name per line
    --list-masks           one mask parameter name per line
    --mask-regex RE        keep only channels matching RE
    --invert               keep the channels NOT matching --mask-regex
    --as-setparameters     print `mask_a=1,mask_b=1`, ready to be handed to
                           combine's --setParameters

So masking the signal regions (keeping only channels whose name ends in _TTCR
or _WCR) is

    list_masks.py -w ws.root --mask-regex '_(TTCR|WCR)$' --invert --as-setparameters
"""
import argparse
import re
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", "-w", required=True)
    p.add_argument("--ws-name", default="w")
    p.add_argument("--mask-regex")
    p.add_argument("--invert", action="store_true")
    p.add_argument("--list-channels", action="store_true")
    p.add_argument("--list-masks", action="store_true")
    p.add_argument("--as-setparameters", action="store_true")
    a = p.parse_args()

    f = ROOT.TFile.Open(a.workspace)
    if not f or f.IsZombie():
        sys.exit("cannot open %s" % a.workspace)
    w = f.Get(a.ws_name)
    if not w:
        sys.exit("no RooWorkspace '%s'" % a.ws_name)

    masks = sorted(v.GetName() for v in w.allVars()
                   if v.GetName().startswith("mask_"))
    channels = [m[len("mask_"):] for m in masks]
    if not masks:
        # No --channel-masks: fall back to the categories of the simultaneous pdf.
        cat = w.cat("CMS_channel")
        if cat:
            channels = []
            for i in range(cat.numTypes()):
                cat.setIndex(i)
                channels.append(cat.getLabel())
            channels.sort()

    if a.mask_regex:
        rx = re.compile(a.mask_regex)
        sel = [c for c in channels if bool(rx.search(c)) != bool(a.invert)]
    else:
        sel = list(channels)

    if a.list_channels:
        print("\n".join(channels))
    elif a.list_masks:
        print("\n".join("mask_" + c for c in sel))
    elif a.as_setparameters:
        if masks:
            print(",".join("mask_%s=1" % c for c in sel))
        # no masks in the workspace -> print nothing, the caller checks for that
    else:
        print("\n".join(sel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
