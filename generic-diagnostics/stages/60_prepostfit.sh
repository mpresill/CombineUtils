# ---------------------------------------------------------------------------
# stage: prepostfit -- pre-fit and post-fit distributions, per channel.
#
# Reads the shapes that the fitdiag stage already saved, so nothing is refitted.
# Three sets per channel: pre-fit, post-fit b-only, post-fit s+b.
#
# While blind the points are the Asimov dataset, so these plots check the model
# and the fit machinery. The control regions are the exception: their data_obs
# is real data, so their pre-fit panel is a genuine data/MC comparison.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "prepostfit already done"; return 0; }

fd="$CARD_OUT/$MODE/fitdiag/fitDiagnostics${TAG}.root"
need_file "$fd" "missing $fd -- run the fitdiag stage first" || return 1

runs "python3 '$HERE/python/plot_prepostfit.py' --input '$fd' \
        --outdir '$STAGE_DIR' --groups-json '$PROCESS_GROUPS' \
        --title '$CARD / $MODE' --logy \
        --report '$STAGE_DIR/yields${TAG}.txt'" \
  || { warn "plot_prepostfit.py failed"; return 1; }

publish "$STAGE_DIR/yields${TAG}.txt"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done
mark_done "$sentinel"
return 0
