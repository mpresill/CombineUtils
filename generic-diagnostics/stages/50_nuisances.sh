# ---------------------------------------------------------------------------
# stage: nuisances -- what the fit did to the nuisance parameters.
#
#   diffNuisances.py      the standard html/text table (b-only vs s+b)
#   plot_pulls.py         pull and constraint plot, sorted, with the
#                         pathologies highlighted:
#                           |pull| > 1     the data want something else
#                           sigma < 0.5    heavily over-constrained
#                           sigma > 1.05   inflated, usually a broken template
#   plot_correlations.py  correlation matrix, and the parameters most
#                         correlated with the POI
#   mlfitNormsToText.py   post-fit normalisation of every process in every bin
#
# On a MODE=asimov Asimov the pulls must be zero by construction: any non-zero
# pull there is a bug, not physics. On MODE=asimovFreq the pulls show what the
# control-region data pull, which is the interesting plot.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "nuisances already done"; return 0; }

fd="$CARD_OUT/$MODE/fitdiag/fitDiagnostics${TAG}.root"
need_file "$fd" "missing $fd -- run the fitdiag stage first" || return 1
cd "$STAGE_DIR" || return 1
rc=0

DN="$CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/diffNuisances.py"

runs "python3 '$DN' --all --abs -f html '$fd' > 'diffNuisances${TAG}.html' 2>'diffNuisances${TAG}.err'" \
  || { warn "diffNuisances.py (html) failed"; rc=1; }
runs "python3 '$DN' --all --abs -f text '$fd' > 'diffNuisances${TAG}.txt' 2>>'diffNuisances${TAG}.err'" \
  || { warn "diffNuisances.py (text) failed"; rc=1; }

runs "python3 \$CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/mlfitNormsToText.py \
      '$fd' > 'postfit_norms${TAG}.txt' 2>'postfit_norms${TAG}.err'" \
  || { warn "mlfitNormsToText.py failed"; rc=1; }

runs "python3 '$HERE/python/plot_pulls.py' --input '$fd' \
        --output-prefix 'pulls${TAG}' --title '$CARD / $MODE' \
        --report 'pulls${TAG}.txt' --json 'pulls${TAG}.json' \
        --expect-zero-pulls $( [ "$MODE" = "asimov" ] && echo 1 || echo 0 )" \
  || { warn "plot_pulls.py failed"; rc=1; }

runs "python3 '$HERE/python/plot_correlations.py' --input '$fd' \
        --output-prefix 'correlations${TAG}' --title '$CARD / $MODE' \
        --poi '$POI' --report 'correlations${TAG}.txt' --top 30" \
  || { warn "plot_correlations.py failed"; rc=1; }

publish "$STAGE_DIR/diffNuisances${TAG}.html" "$STAGE_DIR/diffNuisances${TAG}.txt" \
        "$STAGE_DIR/postfit_norms${TAG}.txt" \
        "$STAGE_DIR/pulls${TAG}.txt" "$STAGE_DIR/pulls${TAG}.json" \
        "$STAGE_DIR/correlations${TAG}.txt"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done

[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
