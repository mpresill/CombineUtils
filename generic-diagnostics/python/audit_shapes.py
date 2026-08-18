#!/usr/bin/env python3
"""Audit the input templates of a shape datacard.

Reads the datacard with combine's own parser, resolves every shape mapping and
inspects the histograms themselves. Reports the pathologies that quietly ruin a
fit and that neither ValidateDatacards.py nor systematicsAnalyzer.py catch in
one place:

  * missing / empty / all-negative templates
  * negative or NaN bin contents
  * bins whose MC statistical error exceeds a threshold
  * shape systematics with a missing Up or Down template
  * one-sided systematics (Up and Down pull the same way)
  * per-bin sign flips w.r.t. the nominal (template goes negative)
  * systematics with a negligible effect everywhere (candidates for pruning)
  * systematics with an implausibly large effect in some bin
  * lnN uncertainties above a threshold

Exit code is 0 even when problems are found: the point is the report, and the
severity call belongs to a human. Use --fail-on-error to make it exit 1 on
anything flagged ERROR.
"""
import argparse
import json
import math
import os
import re
import sys
from collections import OrderedDict

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError

from HiggsAnalysis.CombinedLimit.DatacardParser import (  # noqa: E402
    addDatacardParserOptions,
    parseCard,
)
from optparse import OptionParser  # noqa: E402


# --------------------------------------------------------------------------- #
#  datacard / shape resolution
# --------------------------------------------------------------------------- #
def parse_datacard(path, mass):
    p = OptionParser()
    addDatacardParserOptions(p)
    (opts, _) = p.parse_args([])
    opts.mass = mass
    opts.fileName = path
    with open(path) as fh:
        return parseCard(fh, opts)


def shape_entry(dc, chan, proc):
    """combine's lookup order for the shapes lines."""
    for b, p in ((chan, proc), (chan, "*"), ("*", proc), ("*", "*")):
        if b in dc.shapeMap and p in dc.shapeMap[b]:
            return dc.shapeMap[b][p]
    return None


def expand(pattern, chan, proc, syst, mass):
    return (
        pattern.replace("$CHANNEL", chan)
        .replace("$PROCESS", proc)
        .replace("$SYSTEMATIC", syst)
        .replace("$MASS", str(mass))
    )


class ShapeReader(object):
    """Cache of open TFiles + histogram fetches."""

    def __init__(self, card_dir):
        self.card_dir = card_dir
        self._files = {}

    def _file(self, name):
        if name not in self._files:
            path = name if os.path.isabs(name) else os.path.join(self.card_dir, name)
            f = ROOT.TFile.Open(path)
            if not f or f.IsZombie():
                raise IOError("cannot open shape file %s" % path)
            self._files[name] = f
        return self._files[name]

    def get(self, fname, objname):
        h = self._file(fname).Get(objname)
        if not h:
            return None
        return h.Clone("%s_clone" % objname.replace("/", "_"))


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
def contents(h):
    return [h.GetBinContent(i) for i in range(1, h.GetNbinsX() + 1)]


def errors(h):
    return [h.GetBinError(i) for i in range(1, h.GetNbinsX() + 1)]


def rel(a, b):
    """(a - b) / b, guarding against b == 0."""
    return (a - b) / b if b else 0.0


# --------------------------------------------------------------------------- #
#  the audit
# --------------------------------------------------------------------------- #
class Audit(object):
    def __init__(self, args):
        self.a = args
        self.issues = []          # findings
        self.impacts = []         # per (chan, proc, syst) channel impact
        self.ranking = []
        self.prunable = []
        self.stats = OrderedDict()

    def add(self, level, kind, msg, **kw):
        rec = dict(level=level, kind=kind, message=msg)
        rec.update(kw)
        self.issues.append(rec)

    # -- nominal templates -------------------------------------------------
    def check_nominal(self, chan, proc, h, is_signal):
        vals = contents(h)
        errs = errors(h)
        tot = sum(vals)
        nbins = len(vals)
        where = dict(channel=chan, process=proc)

        if any(math.isnan(v) or math.isinf(v) for v in vals):
            self.add("ERROR", "nan_bin", "nominal template has NaN/Inf bins", **where)
        neg = [i + 1 for i, v in enumerate(vals) if v < 0]
        if neg:
            self.add("ERROR", "negative_bin",
                     "nominal template negative in bin(s) %s" % neg, **where)
        if tot <= 0:
            self.add("ERROR" if is_signal else "WARN", "empty_template",
                     "nominal integral = %.4g" % tot, **where)
            return
        empty = [i + 1 for i, v in enumerate(vals) if v == 0]
        if empty:
            self.add("WARN", "empty_bin",
                     "%d/%d bins are exactly zero (%s)" % (len(empty), nbins, empty),
                     **where)
        # MC statistics of the template itself
        bad_stat = [
            (i + 1, e / v)
            for i, (v, e) in enumerate(zip(vals, errs))
            if v > 0 and e / v > self.a.max_bin_relerr
        ]
        if bad_stat:
            self.add("WARN", "poor_mc_stat",
                     "rel. MC error > %.0f%% in %d bin(s): %s"
                     % (100 * self.a.max_bin_relerr, len(bad_stat),
                        ", ".join("bin%d=%.0f%%" % (b, 100 * r) for b, r in bad_stat[:8])),
                     **where)

    # -- shape systematics -------------------------------------------------
    def check_shape_syst(self, chan, proc, syst, hn, hu, hd, scale, chan_tot):
        """chan_tot: total nominal expectation per bin of this channel.

        Every "is this variation big?" question is answered against chan_tot
        rather than against the process alone: a 200% wiggle on a process
        contributing 1e-5 events cannot move the fit, while a 5% wiggle on the
        dominant background can.
        """
        where = dict(channel=chan, process=proc, systematic=syst)
        if hu is None or hd is None:
            self.add("ERROR", "missing_variation",
                     "missing %s template" % ("Up" if hu is None else "Down"), **where)
            return
        if hu.GetNbinsX() != hn.GetNbinsX() or hd.GetNbinsX() != hn.GetNbinsX():
            self.add("ERROR", "binning_mismatch",
                     "variation has a different number of bins than nominal", **where)
            return

        n, u, d = contents(hn), contents(hu), contents(hd)
        tn, tu, td = sum(n), sum(u), sum(d)
        if tn <= 0:
            return
        ru, rd = rel(tu, tn), rel(td, tn)

        if any(v < 0 for v in u + d):
            self.add("ERROR", "negative_variation",
                     "Up/Down template has negative bins", **where)

        # Largest |variation| in one bin, as a fraction of the total
        # expectation in that bin ("impact"), and as a fraction of this
        # process alone ("max_var").
        impact, imp_bin = 0.0, 0
        max_var, max_bin = 0.0, 0
        flips = []
        for i, (vn, vu, vd) in enumerate(zip(n, u, d)):
            tot_i = chan_tot[i] if i < len(chan_tot) else 0.0
            for vv in (vu, vd):
                if tot_i > 0:
                    imp = abs(vv - vn) / tot_i
                    if imp > impact:
                        impact, imp_bin = imp, i + 1
                if vn > 0:
                    r = abs(rel(vv, vn))
                    if r > max_var:
                        max_var, max_bin = r, i + 1
            if vn > 0 and (vu - vn) * (vd - vn) > 0 and vn > 0.01 * tn:
                flips.append(i + 1)

        self.impacts.append(dict(channel=chan, process=proc, systematic=syst,
                                 impact=impact, bin=imp_bin,
                                 rate_up=ru, rate_down=rd))

        # One-sided: both variations move the yield the same way, so combine
        # symmetrises and the constraint is not the intended one.
        if ru * rd > 0 and min(abs(ru), abs(rd)) > self.a.onesided_thr \
                and impact > self.a.min_impact:
            self.add("WARN", "one_sided",
                     "rate effect one-sided: up %+.1f%%, down %+.1f%% "
                     "(channel impact %.1f%%)" % (100 * ru, 100 * rd, 100 * impact),
                     up=ru, down=rd, impact=impact, **where)

        if impact < self.a.negligible_thr:
            self.add("INFO", "negligible",
                     "largest effect on the channel is %.4f%% -- prunable"
                     % (100 * impact), impact=impact, **where)
        elif impact > self.a.large_thr:
            self.add("WARN", "large_variation",
                     "bin %d: %.0f%% of the total expectation in that bin "
                     "(%.0f%% of this process alone)"
                     % (imp_bin, 100 * impact, 100 * max_var),
                     impact=impact, max_var=max_var, **where)

        if impact > self.a.min_impact and \
                len(flips) > 0.5 * max(1, len([v for v in n if v > 0])):
            self.add("INFO", "one_sided_bins",
                     "Up and Down on the same side of nominal in %d bin(s): %s"
                     % (len(flips), flips[:10]), **where)
        if scale not in (0.0, 1.0):
            self.add("INFO", "scaled_shape",
                     "shape entry is scaled by %g in the card" % scale, **where)

    # -- lnN ---------------------------------------------------------------
    def check_lnN(self, chan, proc, syst, value):
        try:
            if isinstance(value, (list, tuple)):
                lo, hi = float(value[0]), float(value[1])
                eff = max(abs(1.0 / lo - 1.0) if lo else 0.0, abs(hi - 1.0))
            else:
                v = float(value)
                eff = abs(v - 1.0)
        except (TypeError, ValueError):
            return
        if eff > self.a.large_lnN:
            self.add("WARN", "large_lnN",
                     "lnN effect %.0f%%" % (100 * eff),
                     channel=chan, process=proc, systematic=syst)

    # -- driver ------------------------------------------------------------
    def run(self):
        dc = parse_datacard(self.a.card, self.a.mass)
        reader = ShapeReader(os.path.dirname(os.path.abspath(self.a.card)))
        signals = set(dc.signals)

        # ---- pass 1: nominal templates and the per-bin channel totals ------
        nominal = {}          # (chan, proc) -> (fname, syst_pat, hist)
        chan_tot = {}         # chan -> [total expectation per bin]
        for chan in dc.bins:
            for proc in dc.exp[chan]:
                if dc.exp[chan][proc] == 0:
                    self.add("INFO", "zero_rate", "rate line is 0",
                             channel=chan, process=proc)
                ent = shape_entry(dc, chan, proc)
                if ent is None:
                    self.add("INFO", "counting_only",
                             "no shapes line -> treated as counting experiment",
                             channel=chan, process=proc)
                    continue
                fname, nom_pat = ent[0], ent[1]
                syst_pat = ent[2] if len(ent) > 2 else None
                objname = expand(nom_pat, chan, proc, "", self.a.mass)
                hn = reader.get(fname, objname)
                if hn is None:
                    self.add("ERROR", "missing_template",
                             "cannot find %s in %s" % (objname, fname),
                             channel=chan, process=proc)
                    continue
                self.check_nominal(chan, proc, hn, proc in signals)
                nominal[(chan, proc)] = (fname, syst_pat, hn)
                vals = contents(hn)
                acc = chan_tot.setdefault(chan, [0.0] * len(vals))
                for i, v in enumerate(vals):
                    if i < len(acc):
                        acc[i] += max(v, 0.0)

        # ---- pass 2: systematics -------------------------------------------
        n_shape_checks = 0
        for (chan, proc), (fname, syst_pat, hn) in nominal.items():
            if not syst_pat:
                continue
            for (name, _nofloat, pdf, _args, errline) in dc.systs:
                val = errline.get(chan, {}).get(proc, 0)
                if not val:
                    continue
                if pdf in ("lnN", "lnU"):
                    self.check_lnN(chan, proc, name, val)
                    continue
                if not pdf.startswith("shape"):
                    continue
                scale = 1.0 if isinstance(val, (list, tuple)) else float(val)
                hu = reader.get(fname, expand(syst_pat, chan, proc, name + "Up", self.a.mass))
                hd = reader.get(fname, expand(syst_pat, chan, proc, name + "Down", self.a.mass))
                self.check_shape_syst(chan, proc, name, hn, hu, hd, scale,
                                      chan_tot.get(chan, []))
                n_shape_checks += 1

        # ---- systematics negligible in *every* channel and process ---------
        by_syst = {}
        for r in self.impacts:
            by_syst[r["systematic"]] = max(by_syst.get(r["systematic"], 0.0), r["impact"])
        self.ranking = sorted(by_syst.items(), key=lambda kv: -kv[1])
        self.prunable = sorted(k for k, v in by_syst.items()
                               if v < self.a.negligible_thr)
        for name in self.prunable:
            self.add("WARN", "prunable_systematic",
                     "changes no bin anywhere by more than %.3f%% of its content "
                     "-- safe to prune" % (100 * by_syst[name]), systematic=name)

        self.stats["channels"] = len(dc.bins)
        self.stats["processes"] = len(dc.processes)
        self.stats["nuisances"] = len(dc.systs)
        self.stats["templates_checked"] = len(nominal)
        self.stats["shape_variations_checked"] = n_shape_checks
        self.stats["prunable_systematics"] = len(self.prunable)
        for lvl in ("ERROR", "WARN", "INFO"):
            self.stats["n_" + lvl] = sum(1 for i in self.issues if i["level"] == lvl)
        return self


# --------------------------------------------------------------------------- #
#  reporting
# --------------------------------------------------------------------------- #
ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}
COLOR = {"ERROR": "#f8d7da", "WARN": "#fff3cd", "INFO": "#e7f1ff"}


def write_html(audit, path, card):
    rows = sorted(audit.issues, key=lambda r: (ORDER[r["level"]], r["kind"],
                                               r.get("channel", ""), r.get("process", "")))
    with open(path, "w") as f:
        f.write("<!doctype html><meta charset='utf-8'>")
        f.write("<title>shape audit</title>")
        f.write("<style>body{font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;"
                "margin:2em;max-width:1400px}"
                "table{border-collapse:collapse;width:100%}"
                "th,td{border:1px solid #ddd;padding:4px 7px;text-align:left;"
                "vertical-align:top}th{background:#f2f2f2;position:sticky;top:0}"
                "code{font-size:12px}</style>")
        f.write("<h1>Template audit</h1><p><code>%s</code></p>" % card)
        f.write("<h2>Summary</h2><table>")
        for k, v in audit.stats.items():
            f.write("<tr><th>%s</th><td>%s</td></tr>" % (k, v))
        f.write("</table>")
        f.write("<h2>Shape systematics ranked by pre-fit impact</h2>")
        f.write("<p>Largest change of any single bin of the total expectation, "
                "in units of that bin's content.</p><table>"
                "<tr><th>systematic</th><th>max impact</th></tr>")
        for name, imp in audit.ranking:
            f.write("<tr><td>%s</td><td>%.3f%%</td></tr>" % (name, 100 * imp))
        f.write("</table>")
        f.write("<h2>Findings (%d)</h2><table><tr><th>level</th><th>kind</th>"
                "<th>channel</th><th>process</th><th>systematic</th>"
                "<th>message</th></tr>" % len(rows))
        for r in rows:
            f.write("<tr style='background:%s'><td><b>%s</b></td><td>%s</td>"
                    "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (COLOR[r["level"]], r["level"], r["kind"],
                       r.get("channel", ""), r.get("process", ""),
                       r.get("systematic", ""), r["message"]))
        f.write("</table>")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--card", required=True)
    p.add_argument("--mass", default="125")
    p.add_argument("--out-json")
    p.add_argument("--out-html")
    p.add_argument("--plot-dir", help="(reserved) directory for diagnostic plots")
    p.add_argument("--max-bin-relerr", type=float, default=0.30,
                   help="flag template bins whose relative MC error exceeds this")
    p.add_argument("--negligible-thr", type=float, default=0.0005,
                   help="shape systs whose largest effect on any bin of the "
                        "channel total is below this are flagged as prunable")
    p.add_argument("--large-thr", type=float, default=0.20,
                   help="flag shape systs moving a bin of the channel total by "
                        "more than this")
    p.add_argument("--min-impact", type=float, default=0.005,
                   help="ignore shape pathologies whose channel impact is "
                        "below this (they cannot influence the fit)")
    p.add_argument("--top", type=int, default=40,
                   help="how many systematics to list in the impact ranking")
    p.add_argument("--onesided-thr", type=float, default=0.005,
                   help="rate-effect threshold above which one-sidedness is reported")
    p.add_argument("--large-lnN", type=float, default=0.30,
                   help="flag lnN uncertainties larger than this")
    p.add_argument("--fail-on-error", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()

    audit = Audit(a).run()

    for k, v in audit.stats.items():
        print("%-28s %s" % (k, v))
    print("")
    if not a.quiet:
        for r in sorted(audit.issues, key=lambda r: (ORDER[r["level"]], r["kind"])):
            print("[%-5s] %-20s %-22s %-28s %-34s %s"
                  % (r["level"], r["kind"], r.get("channel", "-"),
                     r.get("process", "-")[:28], r.get("systematic", "-")[:34],
                     r["message"]))

    print("")
    print("largest effect of each shape systematic on any single bin of the")
    print("total expectation (a rough pre-fit proxy for its importance):")
    for name, imp in audit.ranking[:a.top]:
        print("  %-45s %6.2f%%" % (name, 100 * imp))
    if audit.prunable:
        print("")
        print("%d systematic(s) below %.3f%% everywhere (prunable): %s"
              % (len(audit.prunable), 100 * a.negligible_thr,
                 ", ".join(audit.prunable)))

    if a.out_json:
        with open(a.out_json, "w") as f:
            json.dump({"card": a.card, "stats": audit.stats,
                       "issues": audit.issues, "ranking": audit.ranking,
                       "prunable": audit.prunable}, f, indent=2)
    if a.out_html:
        write_html(audit, a.out_html, a.card)

    if a.fail_on_error and audit.stats.get("n_ERROR", 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
