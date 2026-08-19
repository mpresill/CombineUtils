# ---------------------------------------------------------------------------
# stage: fitdiag -- FitDiagnostics, the input for almost everything downstream.
#
# One call gives both fits to the same Asimov dataset:
#   fit_b   background only, r fixed to 0  -> can the background model describe
#                                             the control regions on its own?
#   fit_s   signal + background, r free    -> pulls, constraints, correlations
#
# Shapes and normalisations are saved with uncertainties so the nuisances and
# prepostfit stages need no further fitting. That is what makes this the slowest
# single call in the suite (--saveWithUncertainties throws 200 toys per channel
# to get the per-bin uncertainties): about 9 minutes for a single-category card.
# combine's own --plots is deliberately not used; the prepostfit stage draws the
# same distributions from the saved shapes, and better.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "fitdiag already done"; return 0; }

ensure_toy_dataset || return 1
cd "$STAGE_DIR" || return 1
rc=0

runs "combine -M FitDiagnostics -d '$WS' -m $MASS -n '$TAG' $DATA_OPTS \
      --rMin $R_MIN --rMax $R_MAX $(fit_opts) $ROBUST_OPTS \
      --saveShapes --saveWithUncertainties --saveNormalizations \
      --saveOverallShapes --saveNLL --ignoreCovWarning -v 1 \
      > 'fitdiag${TAG}.log' 2>&1" \
  || { warn "FitDiagnostics failed, see $STAGE_DIR/fitdiag${TAG}.log"; rc=1; }

fd="$STAGE_DIR/fitDiagnostics${TAG}.root"
if [ ! -f "$fd" ] && [ "${DRY_RUN:-0}" != "1" ]; then
  warn "no $fd produced"; return 1
fi

# --- did the minimiser actually converge, and is the covariance usable? ----
if [ "${DRY_RUN:-0}" != "1" ] && \
   grep -qiE "fit failed|MINIMIZATION.*FAILED|is not positive definite" "fitdiag${TAG}.log"; then
  warn "the fit log reports a problem:"
  grep -iE "fit failed|MINIMIZATION.*FAILED|is not positive|covariance matrix quality" \
      "fitdiag${TAG}.log" | head -10
  rc=1
fi
[ "${DRY_RUN:-0}" = "1" ] || \
  grep -E "Best fit ${POI}:|covariance matrix quality|Status :" "fitdiag${TAG}.log" | head -8

if [ "${DRY_RUN:-0}" = "1" ]; then
  log "+ (dry run) would write bestfit${TAG}.txt"
else
python3 - "$fd" "$STAGE_DIR/bestfit${TAG}.txt" "$CARD" "$MODE" "$EXPECT_SIGNAL" <<'PY'
import sys, ROOT
ROOT.gROOT.SetBatch(True)
f = ROOT.TFile.Open(sys.argv[1])
L = ["card %s   mode %s   r injected %s" % (sys.argv[3], sys.argv[4], sys.argv[5]), ""]
for tname, label in (("tree_fit_sb", "s+b fit (r free)"),
                     ("tree_fit_b", "b-only fit (r = 0)")):
    t = f.Get(tname) if f else None
    L.append(label)
    if not t or not t.GetEntries():
        L.append("    <missing>")
        continue
    t.GetEntry(0)
    if hasattr(t, "r"):
        L.append("    r          = %+.4f  +%.4f / -%.4f" % (t.r, t.rHiErr, t.rLoErr))
    L.append("    fit_status = %d   (0 = converged)" % t.fit_status)
    for br in ("nll_min", "nll0", "nll_nll0"):
        if hasattr(t, br):
            L.append("    %-10s = %.5f" % (br, getattr(t, br)))
# covariance quality of the s+b fit
fr = f.Get("fit_s")
if fr:
    L.append("")
    L.append("fit_s covQual = %d  (3 = accurate), edm = %.3g, status = %d"
             % (fr.covQual(), fr.edm(), fr.status()))
txt = "\n".join(L)
open(sys.argv[2], "w").write(txt + "\n")
print(txt)
PY
[ $? -eq 0 ] || { warn "writing bestfit${TAG}.txt failed"; rc=1; }
fi

publish "$STAGE_DIR/bestfit${TAG}.txt" "$STAGE_DIR/fitdiag${TAG}.log"
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
