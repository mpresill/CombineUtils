# ---------------------------------------------------------------------------
# stage: validate -- everything that can go wrong before a single fit runs.
#
#   1. ValidateDatacards.py (CombineHarvester): empty/negative shapes, small
#      signal contributions, uncertainties with a large rate effect, bins with
#      only one process, "shape" uncertainties that are really flat, ...
#   2. systematicsAnalyzer.py: browsable table of every nuisance.
#   3. audit_shapes.py (this repo): per-(bin,process,systematic) audit of the
#      input histograms -- negative/zero bins, one-sided variations, sign
#      flips, huge or negligible shape effects, MC-stat quality.
#
# Nothing here touches data beyond the yields already written in the card.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "validate already done (FORCE=1 to redo)"; return 0; }

cd "$STAGE_DIR" || return 1
rc=0

# --- 1. CombineHarvester validation ---------------------------------------
# CombineHarvester prepends the card directory to the shape file name even when
# it is absolute, so hand it a copy with local names (see localize_card.py).
local_card="$(python3 "$HERE/python/localize_card.py" --card "$CARD_PATH" \
                --outdir "$STAGE_DIR/ch_input")"
[ -n "$local_card" ] || { warn "could not localize the datacard"; local_card="$CARD_PATH"; }

runs "ValidateDatacards.py '$local_card' --printLevel 2 --mass '*' \
      --jsonFile '$STAGE_DIR/validation${TAG}.json' > '$STAGE_DIR/validation${TAG}.txt' 2>&1" \
  || { warn "ValidateDatacards.py returned non-zero"; rc=1; }
[ -s "$STAGE_DIR/validation${TAG}.txt" ] && tail -40 "$STAGE_DIR/validation${TAG}.txt"

# --- 2. nuisance table -----------------------------------------------------
runs "python3 \$CMSSW_BASE/src/HiggsAnalysis/CombinedLimit/test/systematicsAnalyzer.py \
      '$CARD_PATH' --all -f html > '$STAGE_DIR/systematics${TAG}.html' 2>'$STAGE_DIR/systematics${TAG}.err'" \
  || { warn "systematicsAnalyzer.py failed (see systematics${TAG}.err)"; rc=1; }

# --- 3. input histogram audit ---------------------------------------------
runs "python3 '$HERE/python/audit_shapes.py' --card '$CARD_PATH' \
        --out-json '$STAGE_DIR/shape_audit${TAG}.json' \
        --out-html '$STAGE_DIR/shape_audit${TAG}.html' \
        --plot-dir '$STAGE_DIR/bad_shapes' \
      | tee '$STAGE_DIR/shape_audit${TAG}.txt'" \
  || { warn "audit_shapes.py failed"; rc=1; }

publish "$STAGE_DIR/validation${TAG}.json" "$STAGE_DIR/validation${TAG}.txt" \
        "$STAGE_DIR/systematics${TAG}.html" \
        "$STAGE_DIR/shape_audit${TAG}.html" "$STAGE_DIR/shape_audit${TAG}.txt"
[ -d "$STAGE_DIR/bad_shapes" ] && publish "$STAGE_DIR/bad_shapes"

[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
