# ---------------------------------------------------------------------------
# stage: extras -- the checks that do not fit anywhere else.
#
#   1. ChannelCompatibilityCheck: one signal strength per analysis category.
#      On an Asimov every category must come back at the injected value; a
#      category that does not is a category whose templates disagree with the
#      combined model.
#
#   2. FastScan: the likelihood as a function of each parameter, one at a time,
#      with everything else fixed. This is the cheapest way to find a template
#      that makes the NLL non-smooth -- kinks, steps and flat directions show up
#      immediately and explain most "the fit does not converge" reports.
#
#   3. Minimiser stability: the same fit repeated with different minimiser
#      settings. If r or its uncertainty moves between them, no downstream
#      number is trustworthy.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "extras already done"; return 0; }

ensure_toy_dataset || return 1
cd "$STAGE_DIR" || return 1
rc=0

# --- 1. ChannelCompatibilityCheck ------------------------------------------
gopts=""; ngroups=0
channels="$(python3 "$HERE/python/list_masks.py" --workspace "$WS" --list-channels)"
for g in "${CCC_GROUPS[@]}"; do
  if echo "$channels" | grep -q -- "$g"; then
    gopts="$gopts -g $g"
    ngroups=$((ngroups + 1))
  fi
done
if [ "$ngroups" -ge 2 ]; then
  runs "combine -M ChannelCompatibilityCheck -d '$WS' -m $MASS -n '_ccc${TAG}' \
        $DATA_OPTS $gopts --saveFitResult --rMin $R_MIN --rMax $R_MAX \
        $(fit_opts) > 'ccc${TAG}.log' 2>&1" \
    && runs "python3 '$HERE/python/plot_ccc.py' \
              --input 'higgsCombine_ccc${TAG}.ChannelCompatibilityCheck.mH${MASS}.root' \
              --poi $POI --title '$CARD / $MODE' \
              --output-prefix 'ccc${TAG}' --report 'ccc${TAG}.txt'" \
    || { warn "ChannelCompatibilityCheck failed, see ccc${TAG}.log"; rc=1; }
else
  log "only $ngroups CCC group(s) present in this card, skipping the compatibility check"
fi

# --- 2. FastScan -----------------------------------------------------------
# FastScan needs a dataset it can point at by name, so it is the one thing that
# cannot work without the shared file.
if [ -n "${TOYFILE:-}" ]; then
  fd="$CARD_OUT/$MODE/fitdiag/fitDiagnostics${TAG}.root"
  fitres=""; [ -f "$fd" ] && fitres="-f '$fd:fit_s'"
  runs "combineTool.py -M FastScan -w '$WS:w' -d '$TOYFILE:toys/toy_asimov' \
        $fitres --match '$FASTSCAN_MATCH' -p 40 -o 'fastscan${TAG}' \
        > 'fastscan${TAG}.log' 2>&1" \
    || { warn "FastScan failed, see fastscan${TAG}.log"; rc=1; }
else
  log "USE_SHARED_TOYS=0, so there is no dataset to hand FastScan; skipping it"
fi

# --- 3. minimiser stability ------------------------------------------------
stability() {  # <tag> <opts>
  runs "combine -M MultiDimFit -d '$WS' -m $MASS -n '$1' --algo singles \
        $DATA_OPTS -P $POI \
        --setParameterRanges ${POI}=${R_MIN},${R_MAX}${RATE_RANGES:+:$RATE_RANGES} \
        $2 > 'stab${1}.log' 2>&1"
}
stability "_stab_robust${TAG}"  "$MINIMIZER_OPTS $ROBUST_OPTS"                        || rc=1
stability "_stab_minos${TAG}"   "$MINIMIZER_OPTS"                                     || rc=1
stability "_stab_strat2${TAG}"  "--cminDefaultMinimizerStrategy 2 $ROBUST_OPTS"        || rc=1

runs "python3 '$HERE/python/compare_fits.py' --poi $POI \
        --title '$CARD / $MODE' --report 'stability${TAG}.txt' \
        --entry 'robustFit (default)=$(combine_out "$STAGE_DIR" "_stab_robust${TAG}" MultiDimFit)' \
        --entry 'MINOS, strategy 0=$(combine_out "$STAGE_DIR" "_stab_minos${TAG}" MultiDimFit)' \
        --entry 'robustFit, strategy 2=$(combine_out "$STAGE_DIR" "_stab_strat2${TAG}" MultiDimFit)'" \
  || { warn "compare_fits.py failed"; rc=1; }

publish "$STAGE_DIR/ccc${TAG}.txt" "$STAGE_DIR/stability${TAG}.txt"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
