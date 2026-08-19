# ---------------------------------------------------------------------------
# stage: crfit -- fit the control regions to REAL DATA.
#
# This is the one check in this suite that uses observed data, and it is
# blind-safe: the signal regions are masked out with the mask_* parameters that
# text2workspace.py --channel-masks created, so only the *_TTCR and *_WCR bins
# enter the likelihood, and those bins already hold real data in the datacards.
# The signal strength is frozen to zero because with the signal regions masked
# it is unconstrained.
#
# What it answers: how far from 1 do the data push the top and W+jets
# normalisations, and does the answer agree between categories? That is the
# most informative number available before unblinding, and the pre-fit control
# region panels from the prepostfit stage are the picture that goes with it.
#
# Mode independent -- there are no toys here.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "crfit already done"; return 0; }

need_file "$WS" "no workspace, run the workspace stage first" || return 1
cd "$STAGE_DIR" || return 1

masks="$(python3 "$HERE/python/list_masks.py" --workspace "$WS" \
           --mask-regex "$CR_SUFFIX_REGEX" --invert --as-setparameters 2>/dev/null)"
if [ -z "$masks" ]; then
  warn "the workspace has no mask_* parameters; rebuild it with FORCE=1 so"
  warn "text2workspace.py runs with --channel-masks. Skipping."
  [ "${DRY_RUN:-0}" = "1" ] || return 1
  masks="<mask_SR>=1"
fi

resolve_parameter_sets || return 1
rates="$RATE_PARAMS"
[ -n "$rates" ] || { warn "no free rate parameters matching $RATE_PARAM_REGEX"; [ "${DRY_RUN:-0}" = "1" ] || return 1; }
log "masking: $masks"
log "fitting: $rates"

runs "combine -M MultiDimFit -d '$WS' -m $MASS -n '_crfit${TAG}' \
      --algo singles --redefineSignalPOIs '$rates' \
      --setParameters ${masks},${POI}=0 --freezeParameters $POI \
      --setParameterRanges $RATE_RANGES \
      $MINIMIZER_OPTS $ROBUST_OPTS --saveFitResult -v 1 \
      > 'crfit${TAG}.log' 2>&1" \
  || { warn "control-region fit failed, see crfit${TAG}.log"; return 1; }

out="$(combine_out "$STAGE_DIR" "_crfit${TAG}" MultiDimFit)"
[ -n "$out" ] || { warn "no MultiDimFit output"; [ "${DRY_RUN:-0}" = "1" ] || return 1; }

runs "python3 '$HERE/python/summarize_crfit.py' --input '$out' \
        --params '$rates' --title '$CARD' \
        --output-prefix 'crfit${TAG}' --report 'crfit${TAG}.txt'" \
  || { warn "summarize_crfit.py failed"; return 1; }

publish "$STAGE_DIR/crfit${TAG}.txt" "$STAGE_DIR/crfit${TAG}.log"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done
mark_done "$sentinel"
return 0
