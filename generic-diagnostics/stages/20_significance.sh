# ---------------------------------------------------------------------------
# stage: significance -- expected significance of the injected signal.
#
# This is the headline blind number. Reported for the mode's Asimov dataset,
# with the local p-value.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "significance already done"; return 0; }

ensure_toy_dataset || return 1
cd "$STAGE_DIR" || return 1

tag="_sig${TAG}"
runs "combine -M Significance -d '$WS' -n '$tag' -m $MASS $DATA_OPTS \
      --rMin $R_MIN --rMax $R_MAX $(fit_opts) -v 1 \
      > 'significance${TAG}.log' 2>&1" \
  || { warn "Significance failed, see $STAGE_DIR/significance${TAG}.log"; return 1; }

out="$(combine_out "$STAGE_DIR" "$tag" Significance)"
[ -n "$out" ] || { warn "no Significance output found"; return 1; }

python3 - "$out" "$STAGE_DIR/significance${TAG}.txt" "$CARD" "$MODE" "$EXPECT_SIGNAL" <<'PY'
import sys, math, ROOT
ROOT.gROOT.SetBatch(True)
f = ROOT.TFile.Open(sys.argv[1]); t = f.Get("limit")
z = [e.limit for e in t]
z = z[0] if z else float("nan")
p = 0.5 * math.erfc(z / math.sqrt(2.0)) if z == z else float("nan")
txt = ("card            %s\nmode            %s\nr injected      %s\n"
       "significance    %.4f\nlocal p-value   %.3g\n"
       % (sys.argv[3], sys.argv[4], sys.argv[5], z, p))
open(sys.argv[2], "w").write(txt)
print(txt)
PY
rc=$?

publish "$STAGE_DIR/significance${TAG}.txt" "$STAGE_DIR/significance${TAG}.log"
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
