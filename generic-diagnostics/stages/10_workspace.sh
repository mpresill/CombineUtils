# ---------------------------------------------------------------------------
# stage: workspace -- build the RooWorkspace once and dump its content.
#
# The dump is the cheapest way to catch the classic mistakes: a POI that is not
# what you think it is, rateParams silently left unbounded, nuisances that ended
# up unconstrained, an unexpected number of autoMCStats parameters.
# ---------------------------------------------------------------------------
sentinel="$CARD_OUT/.workspace.done"
if already_done "$sentinel" && [ -f "$WS" ]; then
  log "workspace already built: $WS"
else
  runs "text2workspace.py '$CARD_PATH' -o '$WS' -m $MASS --channel-masks \
        > '$STAGE_DIR/text2workspace${TAG}.log' 2>&1" \
    || { warn "text2workspace.py failed, see $STAGE_DIR/text2workspace${TAG}.log"; return 1; }
  mark_done "$sentinel"
fi

runs "python3 '$HERE/python/dump_workspace.py' --workspace '$WS' \
        --out-txt '$STAGE_DIR/workspace${TAG}.txt' \
        --out-json '$STAGE_DIR/workspace${TAG}.json' \
      | tee '$STAGE_DIR/workspace_summary${TAG}.txt'" \
  || { warn "dump_workspace.py failed"; return 1; }

publish "$STAGE_DIR/workspace${TAG}.txt" "$STAGE_DIR/workspace${TAG}.json" \
        "$STAGE_DIR/text2workspace${TAG}.log"
return 0
