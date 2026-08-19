# ---------------------------------------------------------------------------
# stage: gof -- goodness of fit against toys.
#
# READ THIS BEFORE QUOTING A P-VALUE FROM HERE.
#
# On these cards a goodness of fit cannot say anything yet, for two independent
# reasons, and the stage checks for both and says so in its report:
#
#   * in the signal regions `data_obs` is the MC prediction itself while blind,
#     so the model fits it essentially perfectly and the test statistic comes
#     out at ~0 with p = 1 by construction;
#   * each control region is a single bin with its own free rate parameter
#     (norm_top, norm_wjet), so the control regions are exactly saturated: zero
#     degrees of freedom, and the statistic is identically 0.
#
# The stage is still worth running now: it exercises the machinery, and once the
# signal regions are unblinded the same commands give the real p-values with no
# changes. Until then the meaningful data check is the `crfit` stage.
#
# Two variants:
#   cr   signal regions masked out, control-region data only
#   all  every channel, data_obs as it sits in the datacard
#
# Three test statistics, because they are sensitive to different failures:
#   saturated  overall normalisation and shape, bin by bin
#   KS         the largest local discrepancy
#   AD         discrepancies in the tails
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "gof already done"; return 0; }

need_file "$WS" "no workspace, run the workspace stage first" || return 1
cd "$STAGE_DIR" || return 1
rc=0

masks="$(python3 "$HERE/python/list_masks.py" --workspace "$WS" \
           --mask-regex "$CR_SUFFIX_REGEX" --invert --as-setparameters 2>/dev/null)"
if [ -z "$masks" ]; then
  warn "the workspace has no mask_* parameters: rebuild it with FORCE=1 so that"
  warn "text2workspace.py is called with --channel-masks; skipping the CR-only GoF"
fi

for algo in "${GOF_ALGOS[@]}"; do
  for variant in cr all; do
    [ "$variant" = "cr" ] && [ -z "$masks" ] && continue
    extra=""; [ "$variant" = "cr" ] && extra="--setParameters $masks"
    t="_gof_${variant}_${algo}${TAG}"
    j="gof_${variant}_${algo}${TAG}"

    # value on the dataset
    runs "combine -M GoodnessOfFit -d '$WS' -m $MASS --algo $algo -n '${t}_data' \
          $(fit_opts) $extra > 'gof${t}_data.log' 2>&1" \
      || { warn "GoF ($variant, $algo) on the dataset failed"; rc=1; continue; }

    # reference distribution from toys thrown at the best fit
    runs "combine -M GoodnessOfFit -d '$WS' -m $MASS --algo $algo -n '${t}_toys' \
          -t $GOF_NTOYS -s -1 --toysFrequentist $(fit_opts) $extra \
          > 'gof${t}_toys.log' 2>&1" \
      || { warn "GoF ($variant, $algo) toys failed"; rc=1; continue; }

    runs "combineTool.py -M CollectGoodnessOfFit \
          --input higgsCombine${t}_data.GoodnessOfFit.mH${MASS}.root \
                  higgsCombine${t}_toys.GoodnessOfFit.mH${MASS}.*.root \
          --output '${j}.json' > 'collect${t}.log' 2>&1" \
      || { warn "CollectGoodnessOfFit ($variant, $algo) failed"; rc=1; continue; }

    runs "plotGof.py '${j}.json' --statistic $algo --mass $MASS.0 \
          -o 'gof_${variant}_${algo}${TAG}' \
          --title-left '$CARD  $variant  ($algo)' \
          > 'plotgof${t}.log' 2>&1" \
      || warn "plotGof.py ($variant, $algo) failed"
  done
done

runs "python3 '$HERE/python/summarize_gof.py' --dir '$STAGE_DIR' \
        --report 'gof_summary${TAG}.txt' \
        --json 'gof_summary${TAG}.json'" || rc=1

publish "$STAGE_DIR/gof_summary${TAG}.txt" "$STAGE_DIR/gof_summary${TAG}.json"
for f in "$STAGE_DIR"/gof*.json "$STAGE_DIR"/gof_*.png "$STAGE_DIR"/gof_*.pdf; do
  [ -e "$f" ] && publish "$f"
done
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
