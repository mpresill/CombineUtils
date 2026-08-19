#!/usr/bin/env python3
"""Build the single page that ties the whole run together.

Walks the scratch area, picks up the machine-readable outputs each stage wrote
(json where available, the text reports otherwise), and produces

    <wwwdir>/index.html

with one row per card and mode: expected significance, best-fit r and its
uncertainty, the statistical/systematic split, the goodness-of-fit p-values, and
the count of flagged pathologies -- plus links into the per-stage directories.

Everything here is read-only: it never runs combine, so it is safe and fast to
re-run at any point while a long job is still going.
"""
import argparse
import glob
import html
import json
import os
import re
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime

STAGES = ["validate", "workspace", "significance", "limits", "fitdiag",
          "nuisances", "prepostfit", "scan", "breakdown", "crfit", "impacts",
          "gof", "extras"]
MODE_INDEPENDENT = {"validate", "workspace", "crfit", "gof"}


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except IOError:
        return None


def grab(pattern, text, cast=float, default=None):
    if not text:
        return default
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return cast(m.group(1))
    except (TypeError, ValueError):
        return default


def collect(outdir, card, mode):
    """Everything worth putting in the table, for one (card, mode)."""
    tag = "_%s_%s" % (card, mode) if mode else "_%s" % card
    base = os.path.join(outdir, card, mode) if mode else os.path.join(outdir, card)
    r = OrderedDict()

    sig = read_text(os.path.join(base, "significance", "significance%s.txt" % tag))
    # Match nan too: a stage that ran and produced nan must not look the same as
    # a stage that never ran. Both used to render as an em-dash.
    r["significance"] = grab(r"significance\s+(nan|[-\d.]+)", sig)
    r["pvalue"] = grab(r"local p-value\s+(nan|[-\d.eE+]+)", sig)

    bf = read_text(os.path.join(base, "fitdiag", "bestfit%s.txt" % tag))
    r["r_fit"] = grab(r"r\s+=\s+([-+\d.]+)", bf)
    r["fit_status"] = grab(r"fit_status = (-?\d+)", bf, int)
    r["covQual"] = grab(r"covQual = (-?\d+)", bf, int)

    scan = read_json(os.path.join(base, "scan", "scan_summary%s.json" % tag))
    if scan:
        r["sigma_total"] = (scan.get("total") or {}).get("sigma")
        bd = scan.get("breakdown") or {}
        r["sigma_stat"] = bd.get("stat")
        r["sigma_syst"] = bd.get("syst")

    bdj = read_json(os.path.join(base, "breakdown", "breakdown%s.json" % tag))
    if bdj:
        r.setdefault("sigma_total", (bdj.get("total") or {}).get("sigma"))
        so = bdj.get("stat_only") or {}
        if so.get("sigma") is not None:
            r["sigma_stat"] = so["sigma"]
        if bdj.get("systematic") is not None:
            r["sigma_syst"] = bdj["systematic"]
        r["top_group"] = (bdj.get("groups") or [{}])[0].get("group")

    pulls = read_json(os.path.join(base, "nuisances", "pulls%s.json" % tag))
    if pulls:
        fl = pulls.get("flags", {})
        r["n_large_pull"] = len(fl.get("large_pull", []))
        r["n_overconstrained"] = len(fl.get("over_constrained", []))
        r["n_inflated"] = len(fl.get("inflated", []))
        r["n_nonzero_asimov"] = len(fl.get("nonzero_on_asimov", []))

    # gof is mode independent: it lives under $OUTDIR/<card>/gof with the
    # card-only tag, whichever mode row we are filling in here.
    card_tag = "_%s" % card
    gof = read_json(os.path.join(outdir, card, "gof",
                                 "gof_summary%s.json" % card_tag))
    if gof:
        bits = []
        for e in gof.get("results", []):
            label = e["name"].replace("gof_", "").replace(card_tag, "")
            bits.append("%s p=%.2f%s" % (label, e["pvalue"],
                                         " (vacuous)" if e["vacuous"] else ""))
        r["gof"] = "; ".join(bits) or None
        r["gof_vacuous"] = bool(gof.get("vacuous"))

    # ValidateDatacards.py writes one key per warning category, each holding
    # the affected (bin, process, systematic) entries.
    val = read_json(os.path.join(outdir, card, "validate",
                                 "validation_%s.json" % card))
    if val:
        r["v_identical"] = len(val.get("uncertTemplSame", {}) or {})
        r["v_onesided"] = len(val.get("uncertVarySameDirect", {}) or {})
        r["v_small_shape"] = len(val.get("smallShapeEff", {}) or {})
        r["v_large_norm"] = len(val.get("largeNormEff", {}) or {})
    audit = read_json(os.path.join(outdir, card, "validate",
                                   "shape_audit_%s.json" % card))
    if audit:
        st = audit.get("stats", {})
        r["audit_errors"] = st.get("n_ERROR")
        r["audit_warnings"] = st.get("n_WARN")
        r["prunable"] = st.get("prunable_systematics")

    stab = read_text(os.path.join(base, "extras", "stability%s.txt" % tag))
    r["stable"] = ("stable against the minimiser" in stab) if stab else None

    ccc = read_text(os.path.join(base, "extras", "ccc%s.txt" % tag))
    r["ccc_pvalue"] = grab(r"p-value = ([\d.]+)", ccc)
    return r


def status_table(outdir):
    """Merge every run's status file.

    Each run of the driver writes its own status.d/<host>.<pid>.tsv, so that two
    runs on two machines cannot lose each other's lines. They are read oldest
    first, letting a later re-run of the same stage supersede an earlier one.
    status.tsv is the pre-status.d layout, still read so old areas keep working.
    """
    paths = glob.glob(os.path.join(outdir, "status.d", "*.tsv"))
    legacy = os.path.join(outdir, "status.tsv")
    if os.path.exists(legacy):
        paths.append(legacy)

    # Order on each row's own timestamp, not on the file's mtime. A file's mtime
    # moves every time any row is appended to it, so with two overlapping runs an
    # older result for one stage can sit in the file that happens to be touched
    # last and overwrite a genuinely newer result for that same stage.
    out = {}
    for path in paths:
        for line in read_text(path).splitlines()[1:]:
            f = line.split("\t")
            if len(f) < 5:
                continue
            key = (f[0], f[1], f[2])
            when = _parse_time(f[5]) if len(f) >= 6 else None
            prev = out.get(key)
            if prev is None or _newer(when, prev[2]):
                out[key] = (f[3], f[4], when)
    return {k: (v[0], v[1]) for k, v in out.items()}


def _parse_time(txt):
    try:
        return datetime.fromisoformat(txt.strip())
    except (ValueError, AttributeError):
        return None


def _newer(a, b):
    """Is timestamp a at least as recent as b? An unparseable time loses to a
    real one, and ties go to the row read later, matching the old behaviour."""
    if a is None:
        return b is None
    if b is None:
        return True
    return a >= b


def fmt(v, spec="%.3f"):
    if v is None:
        return "&mdash;"
    if isinstance(v, bool):
        return "yes" if v else '<b style="color:#c0392b">NO</b>'
    if isinstance(v, float) and v != v:
        return '<b style="color:#c0392b">nan</b>'
    if isinstance(v, str):
        if v.strip().lower() == "nan":
            return '<b style="color:#c0392b">nan</b>'
        return html.escape(v)
    try:
        return spec % v
    except TypeError:
        return html.escape(str(v))


def badge(n, good_is_zero=True):
    if n is None:
        return "&mdash;"
    color = "#27ae60" if (n == 0) == good_is_zero else "#c0392b"
    return '<b style="color:%s">%d</b>' % (color, n)


CSS = """
body{font:13px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     margin:2em auto;max-width:1500px;padding:0 1em;color:#222}
h1{font-size:22px;margin-bottom:.2em}h2{font-size:17px;margin-top:2em}
table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:12.5px}
th,td{border:1px solid #dcdcdc;padding:5px 8px;text-align:right}
th{background:#f4f4f4;text-align:center}
td:first-child,th:first-child,td:nth-child(2){text-align:left}
tr:hover{background:#fafafa}
code{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:12px}
.note{background:#fff8e1;border-left:4px solid #f0c000;padding:.7em 1em;margin:1em 0}
a{color:#1a5fb4}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--outdir", required=True)
    p.add_argument("--wwwdir", required=True)
    p.add_argument("--cards", nargs="+", required=True)
    p.add_argument("--modes", nargs="+", required=True)
    p.add_argument("--include-known", action="store_true",
                   help="also cover cards and modes that earlier runs recorded, "
                        "not just the ones selected now. The page is one file "
                        "for the whole area: without this, a run over one card "
                        "would drop every other card from it.")
    a = p.parse_args()

    st = status_table(a.outdir)
    cards, modes = list(a.cards), list(a.modes)
    if a.include_known:
        for card, mode, _stage in st:
            if card and card not in cards:
                cards.append(card)
            if mode and mode not in modes:
                modes.append(mode)
        cards.sort()
        modes.sort()
    a.cards, a.modes = cards, modes
    H = ["<!doctype html><meta charset='utf-8'>",
         "<title>WV run 3 -- combine diagnostics</title>",
         "<style>%s</style>" % CSS,
         "<h1>Combine diagnostics &mdash; blind checks</h1>"]
    H.append("<p>scratch <code>%s</code><br>web <code>%s</code></p>"
             % (html.escape(a.outdir), html.escape(a.wwwdir)))
    H.append("<div class='note'><b>The analysis is blind.</b> "
             "Every number below comes from an Asimov dataset. "
             "<code>asimov</code> builds it at the pre-fit nuisance values, so "
             "all pulls must be exactly zero and any non-zero pull is a bug. "
             "<code>asimovFreq</code> (<code>--toysFrequentist</code>) first "
             "fits the nuisances to the observed dataset, so its pulls show "
             "what the control-region data want. In the signal regions "
             "<code>data_obs</code> is MC, not data.</div>")

    # ------------------------------------------------------------- results --
    cols = [("significance", "Z", "%.3f"), ("pvalue", "p", "%.2g"),
            ("r_fit", "r", "%+.4f"), ("sigma_total", "&sigma;<sub>tot</sub>", "%.4f"),
            ("sigma_stat", "&sigma;<sub>stat</sub>", "%.4f"),
            ("sigma_syst", "&sigma;<sub>syst</sub>", "%.4f"),
            ("top_group", "dominant syst.", None),
            ("fit_status", "status", "%d"), ("covQual", "covQual", "%d")]
    H.append("<h2>Results</h2><table><tr><th>card</th><th>mode</th>"
             + "".join("<th>%s</th>" % c[1] for c in cols) + "</tr>")
    data = {}
    for card in a.cards:
        for mode in a.modes:
            r = collect(a.outdir, card, mode)
            data[(card, mode)] = r
            H.append("<tr><td>%s</td><td>%s</td>" % (card, mode))
            for key, _, spec in cols:
                H.append("<td>%s</td>" % fmt(r.get(key), spec or "%s"))
            H.append("</tr>")
    H.append("</table>")

    # ------------------------------------------------------------- health ---
    H.append("<h2>Flagged pathologies</h2>")
    H.append("<p>Counts, not verdicts: follow the links and read the reports. "
             "Green means nothing was flagged.</p>")
    H.append("<table><tr><th>card</th><th>mode</th>"
             "<th>identical Up/Down</th><th>one-sided</th><th>large lnN</th>"
             "<th>template errors</th><th>template warnings</th>"
             "<th>prunable systs</th><th>|pull|&gt;1</th><th>over-constrained</th>"
             "<th>inflated</th><th>non-zero pull on Asimov</th>"
             "<th>minimiser stable</th><th>CCC p</th><th>GoF</th></tr>")
    for card in a.cards:
        for mode in a.modes:
            r = data[(card, mode)]
            H.append("<tr><td>%s</td><td>%s</td>" % (card, mode))
            H.append("<td>%s</td>" % fmt(r.get("v_identical"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("v_onesided"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("v_large_norm"), "%d"))
            H.append("<td>%s</td>" % badge(r.get("audit_errors")))
            H.append("<td>%s</td>" % fmt(r.get("audit_warnings"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("prunable"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("n_large_pull"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("n_overconstrained"), "%d"))
            H.append("<td>%s</td>" % fmt(r.get("n_inflated"), "%d"))
            H.append("<td>%s</td>" % badge(r.get("n_nonzero_asimov")
                                           if mode == "asimov" else None))
            H.append("<td>%s</td>" % fmt(r.get("stable")))
            H.append("<td>%s</td>" % fmt(r.get("ccc_pvalue"), "%.3f"))
            H.append("<td>%s</td>" % fmt(r.get("gof")))
            H.append("</tr>")
    H.append("</table>")

    # ------------------------------------------------------------- stages ---
    H.append("<h2>Stage status and links</h2><table><tr><th>card</th><th>mode</th>"
             + "".join("<th>%s</th>" % s for s in STAGES) + "</tr>")
    for card in a.cards:
        for mode in [""] + list(a.modes):
            H.append("<tr><td>%s</td><td>%s</td>" % (card, mode or "&mdash;"))
            for s in STAGES:
                mi = s in MODE_INDEPENDENT
                if (mi and mode) or (not mi and not mode):
                    H.append("<td style='background:#f8f8f8'></td>")
                    continue
                status, secs = st.get((card, mode, s), ("", ""))
                link = "%s/%s/%s" % (card, mode, s) if mode else "%s/%s" % (card, s)
                color = ("#27ae60" if status == "OK"
                         else "#c0392b" if status else "#999")
                label = status or "not run"
                H.append("<td><a href='%s' style='color:%s'>%s</a>%s</td>"
                         % (link, color, label,
                            "<br><small>%ss</small>" % secs if secs else ""))
            H.append("</tr>")
    H.append("</table>")

    H.append("<h2>What each stage checks</h2><ul>")
    for s, doc in [
        ("validate", "datacard and template sanity: ValidateDatacards.py, the "
                     "nuisance table, and a per-template audit (missing or "
                     "negative bins, one-sided or negligible systematics)"),
        ("workspace", "the built workspace: POI, constrained nuisances, free "
                      "rateParams and their ranges, autoMCStats parameters"),
        ("significance", "expected significance and local p-value"),
        ("limits", "AsymptoticLimits, background-only and signal-injected"),
        ("fitdiag", "the b-only and s+b fits, with shapes and normalisations saved"),
        ("nuisances", "pulls, constraints, correlations, post-fit normalisations"),
        ("prepostfit", "pre-fit and post-fit distributions per channel"),
        ("scan", "profile likelihood scan of r, total and stat-only"),
        ("breakdown", "uncertainty contribution of each nuisance group"),
        ("impacts", "per-nuisance impact on r, ranked"),
        ("crfit", "the only stage that touches observed data, and blind-safe: "
                  "the signal regions are masked out and the top and W+jets "
                  "rate parameters are fitted to the control regions alone"),
        ("gof", "goodness of fit against toys. Read the caveat in the report: "
                "with autoMCStats and the CR rate parameters this model can "
                "describe the blinded dataset exactly, so the p-value is "
                "vacuous until unblinding"),
        ("extras", "channel compatibility, FastScan of the likelihood, and "
                   "minimiser stability"),
    ]:
        H.append("<li><b>%s</b> &mdash; %s</li>" % (s, doc))
    H.append("</ul>")

    os.makedirs(a.wwwdir, exist_ok=True)
    out = os.path.join(a.wwwdir, "index.html")
    # Write and rename, so that two runs finishing at once can only ever leave a
    # complete page behind -- never one truncated mid-table for whoever reloads.
    # The PID alone is not unique across hosts, and concurrent runs on separate
    # nodes are the point of all this: two nodes sharing a PID would open the
    # same temp inode, and one rename would publish the other's partial page and
    # break its replace. mkstemp allocates a name no one else holds, in the same
    # directory so the rename stays atomic.
    fd, tmp = tempfile.mkstemp(prefix="index.", suffix=".tmp", dir=a.wwwdir)
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(H))
        os.chmod(tmp, 0o644)          # mkstemp makes it 0600; this is a web area
        os.replace(tmp, out)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
