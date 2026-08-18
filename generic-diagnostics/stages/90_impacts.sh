# ---------------------------------------------------------------------------
# stage: impacts -- the impact of each nuisance on the POI.
#
# combineTool.py -M Impacts in its three steps (initial fit, one fit per
# nuisance, collect), then plotImpacts.py.
#
# The two things to look for:
#   * a nuisance whose impact is comparable to the statistical uncertainty
#     while its pull is large -> that parameter is running the analysis
#   * a nuisance with a big impact and a heavily shrunk post-fit error ->
#     the fit is exploiting a feature of the template rather than measuring
#     something (cross-check against the pulls stage)
#
# The rate parameters are included explicitly. combineTool takes its parameter
# list from the workspace's nuisance set, and text2workspace does not put
# rateParams there, so norm_top/norm_wjet would otherwise be missing from the
# ranking -- despite being the parameters most correlated with r in this fit.
#
# IMPACTS_JOB_MODE=condor sends the per-nuisance fits to HTCondor, which is the
# only sane option for the combined card (150+ nuisances plus MC-stat params).
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "impacts already done"; return 0; }

ensure_toy_dataset || return 1
cd "$STAGE_DIR" || return 1
rc=0

name="imp${TAG}"

nuis="$(python3 "$HERE/python/list_params.py" --workspace "$WS" --nuisances --sep ,)"
rates="$(python3 "$HERE/python/list_params.py" --workspace "$WS" --free --regex '^norm_' --sep ,)"
[ -n "$nuis" ] || { warn "could not list the nuisance parameters"; return 1; }
named="$nuis"; [ -n "$rates" ] && named="$nuis,$rates"
log "$(echo "$named" | tr ',' '\n' | wc -l) parameters in the ranking"

# combineTool.py rebuilds the combine command line and runs it through `sh -c`
# with the quoting stripped, so nothing handed to it may contain shell
# metacharacters. Spell the rate-parameter ranges out by name instead of using
# the rgx{} form the other stages use.
ranges=""
for pn in $(echo "$rates" | tr ',' ' '); do
  ranges="${ranges:+$ranges:}${pn}=${RATEPARAM_MIN:-0.1},${RATEPARAM_MAX:-5}"
done

common="-M Impacts -d '$WS' -m $MASS -n '$name' $DATA_OPTS \
        --named $named \
        --rMin $R_MIN --rMax $R_MAX $MINIMIZER_OPTS $ROBUST_OPTS \
        ${ranges:+--setParameterRanges $ranges}"

if [ "${IMPACTS_JOB_MODE:-interactive}" = "condor" ]; then
  job="--job-mode condor --task-name impacts${TAG} \
       --sub-opts='+JobFlavour = \"$CONDOR_QUEUE\"'"
else
  job="--parallel $NCORES"
fi

runs "combineTool.py $common --doInitialFit > 'impacts_initial${TAG}.log' 2>&1" \
  || { warn "initial impact fit failed, see impacts_initial${TAG}.log"; return 1; }

runs "combineTool.py $common --doFits $job > 'impacts_fits${TAG}.log' 2>&1" \
  || { warn "per-nuisance impact fits failed, see impacts_fits${TAG}.log"; rc=1; }

if [ "${IMPACTS_JOB_MODE:-interactive}" = "condor" ]; then
  log "condor jobs submitted; re-run this stage once the queue is empty"
  log "  watch with: condor_q -nobatch"
  return 0
fi

runs "combineTool.py $common -o 'impacts${TAG}.json' > 'impacts_collect${TAG}.log' 2>&1" \
  || { warn "impact collection failed, see impacts_collect${TAG}.log"; return 1; }

runs "plotImpacts.py -i 'impacts${TAG}.json' -o 'impacts${TAG}' --summary \
      --per-page 40 --cms-label 'Preliminary' \
      > 'plotImpacts${TAG}.log' 2>&1" \
  || { warn "plotImpacts.py failed, see plotImpacts${TAG}.log"; rc=1; }

runs "python3 '$HERE/python/summarize_impacts.py' --input 'impacts${TAG}.json' \
        --poi $POI --title '$CARD / $MODE' \
        --report 'impacts_summary${TAG}.txt' --top 30" \
  || { warn "summarize_impacts.py failed"; rc=1; }

publish "$STAGE_DIR/impacts${TAG}.json" "$STAGE_DIR/impacts_summary${TAG}.txt"
for f in "$STAGE_DIR"/impacts*.pdf "$STAGE_DIR"/*.png; do [ -e "$f" ] && publish "$f"; done

[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
