# ============================================================================
#  common.sh -- helpers shared by every stage. Sourced, never executed.
# ============================================================================

set -o pipefail

# ------------------------------------------------------------- logging ------
_c_red=$'\033[31m'; _c_grn=$'\033[32m'; _c_ylw=$'\033[33m'
_c_blu=$'\033[34m'; _c_off=$'\033[0m'
[ -t 1 ] || { _c_red=; _c_grn=; _c_ylw=; _c_blu=; _c_off=; }

log()   { printf '%s[%s]%s %s\n' "$_c_blu" "$(date +%H:%M:%S)" "$_c_off" "$*"; }
ok()    { printf '%s[ OK ]%s %s\n' "$_c_grn" "$_c_off" "$*"; }
warn()  { printf '%s[WARN]%s %s\n' "$_c_ylw" "$_c_off" "$*" >&2; }
die()   { printf '%s[FAIL]%s %s\n' "$_c_red" "$_c_off" "$*" >&2; exit 1; }

# Echo a command. --named on the combined card carries 211 parameter names and
# turns a stage log into 7 kB of unreadable text per line, so long commands are
# abbreviated on screen and written out in full to commands.log next to the
# stage output, where they stay copy-pasteable.
ECHO_MAX=${ECHO_MAX:-600}
echo_cmd() {
  local c="$1"
  if [ -n "${STAGE_DIR:-}" ] && [ "${DRY_RUN:-0}" != "1" ]; then
    printf '%s\n\n' "$c" >> "$STAGE_DIR/commands.log"
  fi
  if [ "${#c}" -gt "$ECHO_MAX" ] && [ "${DRY_RUN:-0}" != "1" ]; then
    printf '%s+%s %s ... [%d chars, full command in commands.log]\n' \
      "$_c_ylw" "$_c_off" "${c:0:$ECHO_MAX}" "${#c}"
  else
    printf '%s+%s %s\n' "$_c_ylw" "$_c_off" "$c"
  fi
}

# Run a command, echoing it first. Honours DRY_RUN=1.
run() {
  echo_cmd "$*"
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  "$@"
}

# Same, but the command is a single string handed to `bash -c`. Needed
# wherever combine options carry quotes that must survive, e.g.
#   --setParameterRanges 'rgx{norm_.*}'=0,5
runs() {
  echo_cmd "$1"
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  bash -c "$1"
}

# ----------------------------------------------------------- environment ----
setup_combine_env() {
  [ -n "${_COMBINE_ENV_DONE:-}" ] && return 0
  [ -d "$CMSSW_DIR" ] || die "CMSSW_DIR not found: $CMSSW_DIR"
  # shellcheck disable=SC1091
  source /cvmfs/cms.cern.ch/cmsset_default.sh >/dev/null 2>&1 \
    || die "cannot source cmsset_default.sh"
  pushd "$CMSSW_DIR/src" >/dev/null || die "no $CMSSW_DIR/src"
  eval "$(scramv1 runtime -sh 2>/dev/null)" || die "scram runtime failed"
  popd >/dev/null
  command -v combine        >/dev/null || die "combine not in PATH after cmsenv"
  command -v combineTool.py >/dev/null || die "combineTool.py not in PATH"
  export _COMBINE_ENV_DONE=1
  log "using combine from $(command -v combine)"
}

# ------------------------------------------------------------- www area -----
# Create a web directory and drop index.php beside the plots so the CERN web
# server renders a browsable gallery.
mkwww() {
  local d="$1"
  mkdir -p "$d" || return 1
  if [ -n "${WWW_INDEX_PHP:-}" ] && [ -f "$WWW_INDEX_PHP" ] && [ ! -f "$d/index.php" ]; then
    cp "$WWW_INDEX_PHP" "$d/index.php" 2>/dev/null || true
  fi
}

# publish <file> ... -- copy into $STAGE_WWW, creating it on demand.
publish() {
  [ "${DRY_RUN:-0}" = "1" ] && { printf '%s+%s publish %s\n' "$_c_ylw" "$_c_off" "$*"; return 0; }
  local dest="${STAGE_WWW:?STAGE_WWW not set}"
  mkwww "$dest"
  local f
  for f in "$@"; do
    [ -e "$f" ] || { warn "publish: missing $f"; continue; }
    cp -rf "$f" "$dest/" || warn "publish: could not copy $f"
  done
}

# ------------------------------------------------------------- guards -------
# Fail a stage because a prerequisite artefact is missing -- except in a dry
# run, where by construction nothing upstream has been produced and the point
# is to keep going and print the rest of the commands.
need_file() {  # <path> <message>
  [ -f "$1" ] && return 0
  if [ "${DRY_RUN:-0}" = "1" ]; then warn "(dry run) $2 -- continuing"; return 0; fi
  warn "$2"; return 1
}
# Skip a stage whose sentinel file already exists, unless FORCE=1.
already_done() {
  [ "${FORCE:-0}" = "1" ] && return 1
  [ -f "$1" ]
}
mark_done() { [ "${DRY_RUN:-0}" = "1" ] || : > "$1"; }

# ------------------------------------------------- parameter name sets ------
# combine's rgx{} shorthand is expanded against the *nuisance parameter* set, so
# it silently matches nothing for an unconstrained rateParam. Freezing
# `rgx{norm_.*}` therefore looks like it works and is a no-op -- which quietly
# turns the background-normalisation line of the uncertainty breakdown into
# zero. Every parameter set is resolved to explicit names here instead, once per
# card, and cached next to the workspace.
#
# Sets, all comma separated:
#   RATE_PARAMS            free rate parameters (norm_top_*, norm_wjet_*)
#   RATE_RANGES            "p=min,max:p=min,max" for the same, for
#                          --setParameterRanges
#   SYST_PARAMS            constrained nuisances except the autoMCStats ones
#   MCSTAT_PARAMS          the autoMCStats (prop_bin*) parameters
#   STAT_ONLY_LIST         everything above: freeze this for a stat-only fit
#   STAT_PLUS_MCSTAT_LIST  everything but the autoMCStats parameters
resolve_parameter_sets() {
  [ -n "${_PARAM_SETS_CARD:-}" ] && [ "$_PARAM_SETS_CARD" = "$CARD" ] && return 0
  local cache="$CARD_OUT/parameter_sets.sh"
  # The cached lists depend on more than the workspace: change any of the four
  # knobs below and the cache must be rebuilt, or the fits silently run with
  # the previous selection and bounds.
  local sig="$RATE_PARAM_REGEX|$MCSTAT_REGEX|$RATEPARAM_MIN|$RATEPARAM_MAX"
  if [ -f "$cache" ] && [ "$cache" -nt "$WS" ] \
     && grep -qxF "# signature $sig" "$cache"; then
    # shellcheck disable=SC1090
    source "$cache"
  else
    if [ ! -f "$WS" ]; then
      warn "resolve_parameter_sets: no workspace $WS"
      # A dry run has nothing built yet; carry on with placeholders so the rest
      # of the commands still get printed.
      [ "${DRY_RUN:-0}" = "1" ] || return 1
      RATE_PARAMS="<rateParams>"; RATE_RANGES="<rateParam>=$RATEPARAM_MIN,$RATEPARAM_MAX"
      SYST_PARAMS="<nuisances>"; MCSTAT_PARAMS="<prop_bin*>"
      STAT_ONLY_LIST="<nuisances>,<prop_bin*>,<rateParams>"
      STAT_PLUS_MCSTAT_LIST="<nuisances>,<rateParams>"
      export RATE_PARAMS RATE_RANGES SYST_PARAMS MCSTAT_PARAMS \
             STAT_ONLY_LIST STAT_PLUS_MCSTAT_LIST
      return 0
    fi
    local lp="$HERE/python/list_params.py"
    RATE_PARAMS="$(python3 "$lp" -w "$WS" --free --regex "$RATE_PARAM_REGEX" --sep ,)"
    MCSTAT_PARAMS="$(python3 "$lp" -w "$WS" --nuisances --regex "$MCSTAT_REGEX" --sep ,)"
    local all_nuis
    all_nuis="$(python3 "$lp" -w "$WS" --nuisances --sep ,)"
    SYST_PARAMS="$(python3 - "$all_nuis" "$MCSTAT_PARAMS" <<'PYEOF'
import sys
allp = [x for x in sys.argv[1].split(",") if x]
mc = set(x for x in sys.argv[2].split(",") if x)
print(",".join(p for p in allp if p not in mc))
PYEOF
)"
    RATE_RANGES="$(python3 - "$RATE_PARAMS" "$RATEPARAM_MIN" "$RATEPARAM_MAX" <<'PYEOF'
import sys
ps = [x for x in sys.argv[1].split(",") if x]
print(":".join("%s=%s,%s" % (p, sys.argv[2], sys.argv[3]) for p in ps))
PYEOF
)"
    STAT_ONLY_LIST="$(printf '%s' "$SYST_PARAMS${MCSTAT_PARAMS:+,$MCSTAT_PARAMS}${RATE_PARAMS:+,$RATE_PARAMS}")"
    STAT_PLUS_MCSTAT_LIST="$(printf '%s' "$SYST_PARAMS${RATE_PARAMS:+,$RATE_PARAMS}")"
    mkdir -p "$CARD_OUT"
    {
      echo "# generated by resolve_parameter_sets() -- delete to rebuild"
      echo "# signature $sig"
      for v in RATE_PARAMS RATE_RANGES SYST_PARAMS MCSTAT_PARAMS \
               STAT_ONLY_LIST STAT_PLUS_MCSTAT_LIST; do
        printf '%s=%q\n' "$v" "${!v}"
      done
    } > "$cache"
  fi
  export RATE_PARAMS RATE_RANGES SYST_PARAMS MCSTAT_PARAMS \
         STAT_ONLY_LIST STAT_PLUS_MCSTAT_LIST
  _PARAM_SETS_CARD="$CARD"
  log "parameters: $(count_csv "$SYST_PARAMS") syst, $(count_csv "$MCSTAT_PARAMS") MC-stat, $(count_csv "$RATE_PARAMS") rate ($RATE_PARAMS)"
}

count_csv() { [ -z "$1" ] && echo 0 || echo "$1" | tr ',' '\n' | grep -c .; }

# Resolve one NUISANCE_GROUPS regex to explicit parameter names, so that a group
# whose regex matches nothing is reported instead of silently contributing zero.
group_params() {
  local rx="$1"
  python3 "$HERE/python/list_params.py" -w "$WS" --regex "^(${rx})\$" --sep , \
    --any-of nuisances,free
}

# ---------------------------------------------------------- combine bits ----
# Option string shared by everything that fits, so results are comparable.
fit_opts() {
  resolve_parameter_sets >/dev/null 2>&1
  echo "$MINIMIZER_OPTS${RATE_RANGES:+ --setParameterRanges $RATE_RANGES}"
}

# Print the values of one branch of a combine "limit" tree, space separated.
read_limit() {
  python3 - "$1" "${2:-limit}" <<'PY'
import sys, ROOT
ROOT.gROOT.SetBatch(True)
f = ROOT.TFile.Open(sys.argv[1])
t = f.Get("limit") if f else None
if not t:
    sys.exit("no 'limit' tree in %s" % sys.argv[1])
print(" ".join("%.6f" % getattr(e, sys.argv[2]) for e in t))
PY
}

# Locate the file combine produced for a given -n tag and method. combine
# appends the seed whenever toys are used, so glob instead of guessing.
combine_out() {
  local dir="$1" tag="$2" method="$3"
  ls -t "$dir"/higgsCombine"$tag"."$method".mH*.root 2>/dev/null | head -1
}

# NUISANCE_GROUPS accessors.
group_labels() { local g; for g in "${NUISANCE_GROUPS[@]}"; do echo "${g%%:*}"; done; }
group_regex()  { local g; for g in "${NUISANCE_GROUPS[@]}"; do
                   [ "${g%%:*}" = "$1" ] && { echo "${g#*:}"; return 0; }
                 done; return 1; }

# ---------------------------------------------------------- toy dataset -----
# Every stage must fit *the same* dataset, otherwise the uncertainty breakdown
# and the impacts are not comparable. So the Asimov dataset is generated once
# per (card, mode) with GenerateOnly --saveToys and then handed to every
# subsequent call via `--toysFile ... -t -1`.
#
# For MODE=asimov     that is the pre-fit Asimov.
# For MODE=asimovFreq the nuisances are first fitted to the observed dataset,
#                     so the Asimov is built at their post-fit values. Note
#                     that while blind only the control regions carry real
#                     data; the signal-region "data_obs" is MC.
#
# Sets DATA_OPTS (to be appended to every combine command) and TOYFILE.
# True when the GenerateOnly output really holds the dataset combine will look
# for with `-t -1 --toysFile`.
toyfile_has_dataset() {
  python3 - "$1" <<'PYEOF' 2>/dev/null
import sys, ROOT
ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kFatal
f = ROOT.TFile.Open(sys.argv[1])
if not f or f.IsZombie():
    sys.exit(1)
d = f.Get("toys")
sys.exit(0 if d and d.Get("toy_asimov") else 1)
PYEOF
}

ensure_toy_dataset() {
  # The simple path: no shared file, every call builds its own Asimov from -t -1.
  if [ "${USE_SHARED_TOYS:-1}" != "1" ]; then
    TOYFILE=""
    DATA_OPTS="$TOY_OPTS --expectSignal $EXPECT_SIGNAL"
    export TOYFILE DATA_OPTS
    log "dataset: built per call ($TOY_OPTS), USE_SHARED_TOYS=0"
    return 0
  fi
  local dir="$CARD_OUT/${MODE}/toys"
  local tag="_toy${TAG}"
  mkdir -p "$dir"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    TOYFILE="$dir/higgsCombine${tag}.GenerateOnly.mH${MASS}.${SEED}.root"
    DATA_OPTS="-t -1 --toysFile $TOYFILE --expectSignal $EXPECT_SIGNAL"
    export TOYFILE DATA_OPTS
    return 0
  fi
  TOYFILE="$(combine_out "$dir" "$tag" GenerateOnly)"
  # A GenerateOnly that fails still leaves a small, *empty* output file behind.
  # Reusing it poisons every later stage: combine reports "Toy toy_asimov not
  # found", falls back to nothing, and the failure only surfaces several stages
  # downstream as an unreadable combineTool traceback. So never trust the glob
  # alone -- open the file and check the dataset is really in it.
  if [ -n "$TOYFILE" ] && ! toyfile_has_dataset "$TOYFILE"; then
    warn "$TOYFILE contains no toys/toy_asimov -- discarding it and regenerating"
    rm -f "$TOYFILE"
    TOYFILE=""
  fi
  if [ -z "$TOYFILE" ] || [ "${FORCE:-0}" = "1" ]; then
    log "generating the $MODE dataset once for $CARD"
    if ! runs "cd '$dir' && combine -M GenerateOnly -d '$WS' -n '$tag' -m $MASS \
          $TOY_OPTS --expectSignal $EXPECT_SIGNAL --saveToys -s $SEED \
          $MINIMIZER_OPTS > gen.log 2>&1"; then
      warn "GenerateOnly failed, see $dir/gen.log"
      tail -3 "$dir/gen.log" 2>/dev/null | sed 's/^/       /' >&2
      # Do not leave the stub behind for the next run to pick up.
      rm -f "$(combine_out "$dir" "$tag" GenerateOnly)"
      return 1
    fi
    TOYFILE="$(combine_out "$dir" "$tag" GenerateOnly)"
  fi
  [ -n "$TOYFILE" ] || { warn "no toy file produced in $dir"; return 1; }
  if ! toyfile_has_dataset "$TOYFILE"; then
    warn "GenerateOnly produced $TOYFILE but it holds no dataset; see $dir/gen.log"
    rm -f "$TOYFILE"
    return 1
  fi
  # -t -1 makes combine read toys/toy_asimov out of TOYFILE.
  DATA_OPTS="-t -1 --toysFile $TOYFILE --expectSignal $EXPECT_SIGNAL"
  export TOYFILE DATA_OPTS
  log "dataset: $TOYFILE"
}

# ------------------------------------------------- best-fit snapshot --------
# Shared by the likelihood scan and the uncertainty breakdown: a workspace with
# the s+b best fit stored as the "MultiDimFit" snapshot, so that freezing a
# group of nuisances freezes them at their post-fit values (the standard
# combine recipe) rather than at zero.
ensure_bestfit_snapshot() {
  resolve_parameter_sets || return 1
  local dir="$CARD_OUT/${MODE}/bestfit"
  local tag="_bestfit${TAG}"
  mkdir -p "$dir"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    SNAPSHOT_WS="$dir/higgsCombine${tag}.MultiDimFit.mH${MASS}.${SEED}.root"
    export SNAPSHOT_WS
    return 0
  fi
  SNAPSHOT_WS="$(combine_out "$dir" "$tag" MultiDimFit)"
  if [ -z "$SNAPSHOT_WS" ] || [ "${FORCE:-0}" = "1" ]; then
    log "building the best-fit snapshot for $CARD/$MODE"
    runs "cd '$dir' && combine -M MultiDimFit -d '$WS' -n '$tag' -m $MASS \
          --algo none --saveWorkspace $DATA_OPTS \
          --setParameterRanges ${POI}=${R_MIN},${R_MAX}${RATE_RANGES:+:$RATE_RANGES} \
          $MINIMIZER_OPTS $ROBUST_OPTS > bestfit.log 2>&1" \
      || { warn "best-fit snapshot failed, see $dir/bestfit.log"; return 1; }
    SNAPSHOT_WS="$(combine_out "$dir" "$tag" MultiDimFit)"
  fi
  [ -n "$SNAPSHOT_WS" ] || { warn "no snapshot workspace in $dir"; return 1; }
  export SNAPSHOT_WS
  log "snapshot: $SNAPSHOT_WS"
}
