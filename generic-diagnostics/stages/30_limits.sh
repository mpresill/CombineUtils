# ---------------------------------------------------------------------------
# stage: limits -- AsymptoticLimits on the signal strength.
#
# Two numbers, both blind:
#   blind     expected limits from a background-only Asimov, data never touched
#   injected  limits on this mode's Asimov with r = $EXPECT_SIGNAL injected
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "limits already done"; return 0; }

ensure_toy_dataset || return 1
cd "$STAGE_DIR" || return 1
rc=0

runs "combine -M AsymptoticLimits -d '$WS' -n '_lim_blind${TAG}' -m $MASS \
      --run blind --rMin 0 --rMax $R_MAX $(fit_opts) \
      > 'limit_blind${TAG}.log' 2>&1" \
  || { warn "blind AsymptoticLimits failed"; rc=1; }

runs "combine -M AsymptoticLimits -d '$WS' -n '_lim_injected${TAG}' -m $MASS \
      $DATA_OPTS --rMin 0 --rMax $R_MAX $(fit_opts) \
      > 'limit_injected${TAG}.log' 2>&1" \
  || { warn "injected AsymptoticLimits failed"; rc=1; }

blind="$(combine_out "$STAGE_DIR" "_lim_blind${TAG}" AsymptoticLimits)"
inj="$(combine_out "$STAGE_DIR" "_lim_injected${TAG}" AsymptoticLimits)"

python3 - "$STAGE_DIR/limits${TAG}.txt" "$CARD" "$MODE" "${blind:-}" "${inj:-}" <<'PY'
import sys, ROOT
ROOT.gROOT.SetBatch(True)
QUANT = {0.025: "-2sigma", 0.16: "-1sigma", 0.5: "median",
         0.84: "+1sigma", 0.975: "+2sigma", -1.0: "observed(Asimov)"}
def read(path):
    if not path:
        return []
    f = ROOT.TFile.Open(path)
    t = f.Get("limit") if f else None
    return [] if not t else [(round(e.quantileExpected, 3), e.limit) for e in t]
lines = ["card %s   mode %s" % (sys.argv[2], sys.argv[3]), ""]
for label, path in (("background-only Asimov (--run blind)", sys.argv[4]),
                    ("signal-injected Asimov", sys.argv[5])):
    lines.append(label)
    rows = read(path)
    if not rows:
        lines.append("    <no result>")
    for q, v in rows:
        lines.append("    %-18s r < %.4f" % (QUANT.get(q, "q=%.3f" % q), v))
    lines.append("")
txt = "\n".join(lines)
open(sys.argv[1], "w").write(txt)
print(txt)
PY

publish "$STAGE_DIR/limits${TAG}.txt" "$STAGE_DIR/limit_blind${TAG}.log" \
        "$STAGE_DIR/limit_injected${TAG}.log"
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
