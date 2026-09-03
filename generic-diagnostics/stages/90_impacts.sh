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

need_file "$WS" "no workspace, run the workspace stage first" || return 1
nuis="$(python3 "$HERE/python/list_params.py" --workspace "$WS" --nuisances --sep , 2>/dev/null)"
rates="$(python3 "$HERE/python/list_params.py" --workspace "$WS" --free --regex '^norm_' --sep , 2>/dev/null)"
if [ -z "$nuis" ]; then
  warn "could not list the nuisance parameters"
  [ "${DRY_RUN:-0}" = "1" ] || return 1
  nuis="<nuisances>"
fi
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

# combineTool exits 0 even when the initial fit produced nothing, and then dies
# 200 fits later inside the collect step with an unreadable traceback. Check it
# here, where the message can still say what went wrong.
initial="$STAGE_DIR/higgsCombine_initialFit_${name}.MultiDimFit.mH${MASS}.root"
if [ "${DRY_RUN:-0}" != "1" ]; then
  if ! python3 "$HERE/python/valid_fits.py" --dir "$STAGE_DIR" --name "$name" \
        --params "$POI" --initial "$initial" --print good >/dev/null; then
    warn "the initial fit is empty -- see $STAGE_DIR/impacts_initial${TAG}.log"
    grep -m2 -E "not found|does not exist|Error" "impacts_initial${TAG}.log" 2>/dev/null \
      | sed 's/^/       /' >&2
    return 1
  fi
fi

# The per-parameter fits from an earlier run are reused when all of them are
# present -- that is what makes a re-run, and the two-pass condor mode below,
# cheap. They may only be reused if they were fitted to the workspace and the
# dataset in use *now*. A regenerated Asimov, or a rebuilt workspace, leaves
# 200 perfectly readable .root files behind whose numbers belong to a different
# fit, and combineTool collects them into the json without a word: the ranking
# then mixes a fresh initial fit with stale per-parameter fits and the pulls it
# shows are not the pulls of any single fit. Drop those first, so the count
# below only sees fits that are actually current.
#
# FORCE=1 must reach them too. It only ever bypassed already_done, so a forced
# re-run redid the initial fit and the collect and then quietly reused the same
# old per-parameter fits -- which is exactly how a run meant to apply a fix
# ended up republishing the results the fix was supposed to correct.
stale=0
for f in higgsCombine_paramFit_"${name}"_*.root; do
  [ -e "$f" ] || continue
  if [ "${FORCE:-0}" = "1" ]; then rm -f "$f"; stale=$((stale + 1)); continue; fi
  for ref in "$WS" "${TOYFILE:-}"; do
    [ -n "$ref" ] && [ -f "$ref" ] && [ "$ref" -nt "$f" ] || continue
    rm -f "$f"; stale=$((stale + 1)); break
  done
done
if [ "$stale" -gt 0 ]; then
  if [ "${FORCE:-0}" = "1" ]; then
    warn "FORCE=1: discarded $stale per-parameter fits, refitting them"
  else
    warn "$stale per-parameter fits predate the workspace or the $MODE dataset -- refitting them"
  fi
fi

# On condor the stage has to run twice: once to submit, once to collect. Decide
# which of the two this is by counting the per-parameter fit outputs that are
# already on disk, otherwise a re-run just resubmits the same jobs for ever and
# the json is never produced.
want=$(echo "$named" | tr ',' '\n' | grep -c .)
have=$(ls higgsCombine_paramFit_"${name}"_*.root 2>/dev/null | wc -l)

if [ "$have" -ge "$want" ]; then
  log "$have/$want per-parameter fits already present, collecting"
else
  # combineTool returns non-zero if *any* of the fits failed. That is a warning,
  # not a stage failure: whether enough of them succeeded is decided by counting
  # the outputs below.
  runs "combineTool.py $common --doFits $job > 'impacts_fits${TAG}.log' 2>&1" \
    || warn "some per-nuisance fits reported an error, see impacts_fits${TAG}.log"
  if [ "${IMPACTS_JOB_MODE:-interactive}" = "condor" ]; then
    log "$want condor jobs submitted ($have already done); re-run this stage"
    log "once the queue is empty and it will collect instead of resubmitting"
    log "  watch with: condor_q -nobatch"
    return 0
  fi
  have=$(ls higgsCombine_paramFit_"${name}"_*.root 2>/dev/null | wc -l)
  [ "$have" -ge "$want" ] || warn "only $have/$want per-parameter fits produced"
fi

# One parameter whose fit failed must not cost the whole ranking. Collect over
# the parameters that actually produced a usable fit and name the rest.
collect_named="$named"
if [ "${DRY_RUN:-0}" != "1" ]; then
  python3 "$HERE/python/valid_fits.py" --dir "$STAGE_DIR" --name "$name" \
      --params "$named" --print report | tee "missing_fits${TAG}.txt"
  good="$(python3 "$HERE/python/valid_fits.py" --dir "$STAGE_DIR" --name "$name" \
            --params "$named" --print good)"
  bad="$(python3 "$HERE/python/valid_fits.py" --dir "$STAGE_DIR" --name "$name" \
            --params "$named" --print bad)"
  if [ -z "$good" ]; then
    warn "not one per-parameter fit succeeded; see impacts_fits${TAG}.log"
    return 1
  fi
  if [ -n "$bad" ]; then
    warn "$(count_csv "$bad") of $(count_csv "$named") parameters have no usable fit;"
    warn "ranking the remaining $(count_csv "$good"). Names in missing_fits${TAG}.txt"
    collect_named="$good"
  fi
fi

collect_common="${common/--named $named/--named $collect_named}"
runs "combineTool.py $collect_common -o 'impacts${TAG}.json' > 'impacts_collect${TAG}.log' 2>&1" \
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
[ -f "$STAGE_DIR/missing_fits${TAG}.txt" ] && publish "$STAGE_DIR/missing_fits${TAG}.txt"
for f in "$STAGE_DIR"/impacts*.pdf "$STAGE_DIR"/*.png; do [ -e "$f" ] && publish "$f"; done

[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
