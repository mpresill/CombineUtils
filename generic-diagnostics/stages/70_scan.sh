# ---------------------------------------------------------------------------
# stage: scan -- profile likelihood scan of the POI.
#
# Two curves on one plot:
#   total      all nuisances profiled
#   stat only  every constrained nuisance and rate parameter frozen at its
#              post-fit value (the snapshot), so the difference in quadrature
#              is the systematic component. The parameters are frozen by name,
#              not with rgx{} -- see resolve_parameter_sets in lib/common.sh.
#
# The shape of the total curve is itself a diagnostic: kinks, plateaux or a
# non-parabolic minimum mean the minimiser is struggling somewhere.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "scan already done"; return 0; }

ensure_toy_dataset || return 1
ensure_bestfit_snapshot || return 1
cd "$STAGE_DIR" || return 1
rc=0

scan() {  # <tag> [<parameters to freeze>]
  # The freeze list is single quoted: it contains rgx{...}, which bash -c would
  # otherwise try to interpret.
  runs "combine -M MultiDimFit -d '$SNAPSHOT_WS' -w w --snapshotName MultiDimFit \
        -m $MASS -n '$1' --algo grid --points $SCAN_POINTS --alignEdges 1 \
        $DATA_OPTS -P $POI --floatOtherPOIs 1 --saveNLL \
        --setParameterRanges ${POI}=${SCAN_RANGE}${RATE_RANGES:+:$RATE_RANGES} \
        $MINIMIZER_OPTS ${2:+--freezeParameters '$2'} > 'scan${1}.log' 2>&1"
}

scan "_scan_total${TAG}"                            || { warn "total scan failed";     rc=1; }
scan "_scan_stat${TAG}" "$STAT_ONLY_LIST"           || { warn "stat-only scan failed"; rc=1; }

total="$(combine_out "$STAGE_DIR" "_scan_total${TAG}" MultiDimFit)"
stat="$(combine_out  "$STAGE_DIR" "_scan_stat${TAG}"  MultiDimFit)"

if [ -n "$total" ]; then
  # The CMS-standard rendering. It is allowed to fail: plot_scan.py below
  # produces the same information and the numbers we actually quote.
  runs "plot1DScan.py '$total' --POI $POI \
        ${stat:+--others '$stat:stat only:2'} ${stat:+--breakdown 'syst,stat'} \
        --main-label 'total' -o 'scan${TAG}' > 'plot1DScan${TAG}.log' 2>&1" \
    || warn "plot1DScan.py failed, see plot1DScan${TAG}.log"
  runs "python3 '$HERE/python/plot_scan.py' --main '$total' ${stat:+--stat '$stat'} \
        --poi $POI --title '$CARD / $MODE' --output-prefix 'nll${TAG}' \
        --report 'scan_summary${TAG}.txt'" \
    || { warn "plot_scan.py failed"; rc=1; }
fi

# plot_scan.py writes <report basename>.json beside the report.
publish "$STAGE_DIR/scan_summary${TAG}.txt"
[ -f "$STAGE_DIR/scan_summary${TAG}.json" ] && publish "$STAGE_DIR/scan_summary${TAG}.json"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
