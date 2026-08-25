#!/usr/bin/env bash
# ============================================================================
#  run_diagnostics.sh -- blind combine diagnostics driver.
#
#  Runs a configurable list of stages over a list of datacards, each in one or
#  more Asimov "modes", and publishes every plot/table to a web area.
#
#    ./run_diagnostics.sh --list
#    ./run_diagnostics.sh -c boosted_e -s validate,workspace,significance
#    ./run_diagnostics.sh -n                     # dry run: print commands only
#                                                # (stage scaffolding -- mkdir,
#                                                #  parameter listing -- still runs)
#    ./run_diagnostics.sh                        # everything, both modes
#
#  Configuration lives in config.sh.
# ============================================================================

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/config.sh"
# shellcheck disable=SC1091
source "$HERE/lib/common.sh"

# Ordered list of stages. Each maps to stages/<n>_<name>.sh
STAGE_ORDER=(validate workspace significance limits fitdiag nuisances \
             prepostfit scan breakdown crfit impacts gof extras)
# Stages that do not depend on the Asimov flavour -- run once per card.
# gof belongs here: both its statistic and its toys come from the workspace
# dataset, so running it per mode only produced two independently fluctuated
# p-values for the same test.
MODE_INDEPENDENT=" validate workspace crfit gof "

declare -A STAGE_DOC=(
  [validate]="datacard sanity: ValidateDatacards.py, systematicsAnalyzer, shape/rate audit"
  [workspace]="text2workspace.py + dump of POI, nuisances, rateParams, MC-stat params"
  [significance]="expected significance for the injected signal"
  [limits]="AsymptoticLimits (expected only, --run blind) on r"
  [fitdiag]="FitDiagnostics: b-only and s+b fits, shapes and normalisations saved"
  [nuisances]="pulls/constraints (diffNuisances + plot), correlation matrix, post-fit norms"
  [prepostfit]="pre-fit and post-fit distributions per channel, with uncertainty bands"
  [scan]="likelihood scan of r (total vs stat-only) via MultiDimFit --algo grid"
  [breakdown]="uncertainty breakdown by freezing nuisance groups"
  [impacts]="per-nuisance impacts on r (+ grouped impact summary)"
  [crfit]="control-region-only fit to real data: the rateParams (blind-safe)"
  [gof]="goodness of fit vs toys; the control-region-only variant tests real data"
  [extras]="ChannelCompatibilityCheck, FastScan of the NLL, minimiser stability"
)

usage() {
  cat <<EOF
usage: $(basename "$0") [options]

  -c, --cards LIST     comma/space separated card names   (default: ${CARDS[*]})
  -m, --modes LIST     asimov and/or asimovFreq           (default: ${MODES[*]})
  -s, --stages LIST    stages to run, or 'all'            (default: all)
  -j, --ncores N       --parallel for combineTool         (default: $NCORES)
      --condor         send the per-nuisance impact fits to HTCondor
  -f, --force          re-run stages that already completed
  -n, --dry-run        print the combine/plot commands instead of running
                       them; nothing is fitted and nothing is published
  -k, --keep-going     do not stop the card on a failing stage (default: on)
  -x, --stop-on-error  abort the whole run on the first failing stage
  -l, --list           list the stages and exit
  -h, --help           this message

Outputs
  scratch : $OUTDIR
  web     : $WWWDIR
EOF
}

list_stages() {
  printf '%-14s %s\n' STAGE DESCRIPTION
  local s
  for s in "${STAGE_ORDER[@]}"; do
    local mi=""; [[ "$MODE_INDEPENDENT" == *" $s "* ]] && mi=" (per card only)"
    printf '%-14s %s%s\n' "$s" "${STAGE_DOC[$s]}" "$mi"
  done
}

SEL_STAGES=("${STAGE_ORDER[@]}")
KEEP_GOING=1

# Options that take a value must be told so: without this a trailing "--cards"
# leaves $2 unset, `shift 2` fails, and the loop spins forever.
need_arg() { [ $# -ge 2 ] || die "option '$1' needs an argument (try --help)"; }

while [ $# -gt 0 ]; do
  case "$1" in
    -c|--cards)   need_arg "$@"; IFS=', ' read -r -a CARDS  <<< "$2"; shift 2 ;;
    -m|--modes)   need_arg "$@"; IFS=', ' read -r -a MODES  <<< "$2"; shift 2 ;;
    -s|--stages)  need_arg "$@"
                  if [ "$2" = "all" ]; then SEL_STAGES=("${STAGE_ORDER[@]}")
                  else IFS=', ' read -r -a SEL_STAGES <<< "$2"; fi; shift 2 ;;
    -j|--ncores)  need_arg "$@"; NCORES="$2"; shift 2 ;;
    --condor)     IMPACTS_JOB_MODE=condor; shift ;;
    -f|--force)   FORCE=1; shift ;;
    -n|--dry-run) DRY_RUN=1; shift ;;
    -k|--keep-going)    KEEP_GOING=1; shift ;;
    -x|--stop-on-error) KEEP_GOING=0; shift ;;
    -l|--list)    list_stages; exit 0 ;;
    -h|--help)    usage; exit 0 ;;
    *) die "unknown option '$1' (try --help)" ;;
  esac
done

export FORCE DRY_RUN NCORES IMPACTS_JOB_MODE

# Validate the stage selection up front rather than failing half way through.
for s in "${SEL_STAGES[@]}"; do
  [ -n "${STAGE_DOC[$s]:-}" ] || die "unknown stage '$s' (try --list)"
done
for m in "${MODES[@]}"; do toy_opts_for_mode "$m" >/dev/null || exit 1; done

setup_combine_env
mkdir -p "$OUTDIR" || die "cannot create OUTDIR=$OUTDIR"
# Deliberately no index.php at the top level: index.html is the summary page
# and the web server would otherwise serve the php gallery instead.
[ "${DRY_RUN:-0}" = "1" ] || mkdir -p "$WWWDIR" || die "cannot create WWWDIR=$WWWDIR"

# Each run appends to its own file rather than to one shared status.tsv. Two
# runs on different cards are a normal thing to want (one lxplus node per card),
# and concurrent appends to a single file on AFS can lose lines: AFS resolves
# write conflicts per file, not per record, so the second closer wins outright.
# Separate files also mean the end-of-run failure list below covers this run
# only, with no line arithmetic.
STATUS_DIR="$OUTDIR/status.d"
mkdir -p "$STATUS_DIR" || die "cannot create $STATUS_DIR"
# hostname+PID is not unique over time: PIDs get reused, and a later run landing
# on a recycled PID would truncate the earlier run's file and drop its stages
# from the merged summary. mktemp allocates the name atomically instead, so a
# status file, once written, is never reopened by anything.
if [ "${DRY_RUN:-0}" != "1" ]; then
  STATUS_FILE="$(mktemp "$STATUS_DIR/$(hostname -s).$(date +%Y%m%dT%H%M%S).XXXXXX.tsv")" \
    || die "cannot create a status file in $STATUS_DIR"
  printf 'card\tmode\tstage\tstatus\tseconds\tstarted\n' > "$STATUS_FILE"
else
  STATUS_FILE="$STATUS_DIR/(dry run)"
fi

record() {  # card mode stage status seconds
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$(date -Is)" >> "$STATUS_FILE"
}

# ---------------------------------------------------------------------------
# run_stage <card> <mode> <stage>
# ---------------------------------------------------------------------------
run_stage() {
  local card="$1" mode="$2" stage="$3"
  local script
  script="$(ls "$HERE"/stages/[0-9][0-9]_"$stage".sh 2>/dev/null | head -1)"
  [ -n "$script" ] || { warn "no script for stage '$stage', skipping"; return 0; }

  export CARD="$card"
  export STAGE="$stage"
  export CARD_PATH="$CARD_DIR/$card/$CARD_FILE"
  export CARD_OUT="$OUTDIR/$card"
  export WS="$CARD_OUT/workspace.root"
  export MODE="$mode"
  export TOY_OPTS; TOY_OPTS="$(toy_opts_for_mode "${mode:-asimov}")"
  if [ -n "$mode" ]; then
    export STAGE_DIR="$CARD_OUT/$mode/$stage"
    export STAGE_WWW="$WWWDIR/$card/$mode/$stage"
    export TAG="_${card}_${mode}"
  else
    export STAGE_DIR="$CARD_OUT/$stage"
    export STAGE_WWW="$WWWDIR/$card/$stage"
    export TAG="_${card}"
  fi

  if [ ! -f "$CARD_PATH" ]; then
    warn "missing datacard $CARD_PATH"
    record "$card" "$mode" "$stage" MISSING_CARD 0
    [ "$KEEP_GOING" = "1" ] || die "aborting (--stop-on-error)"
    return 0
  fi

  mkdir -p "$STAGE_DIR"
  local t0 rc
  t0=$SECONDS
  log "=== $card ${mode:+/$mode} :: $stage ==="
  if [ "${DRY_RUN:-0}" = "1" ]; then
    ( source "$script" )
    rc=$?
  else
    ( source "$script" ) 2>&1 | tee "$STAGE_DIR/stage.log"
    rc=${PIPESTATUS[0]}
  fi
  local dt=$(( SECONDS - t0 ))
  if [ "$rc" -eq 0 ]; then
    ok "$card ${mode:+/$mode} :: $stage  (${dt}s)"
    record "$card" "$mode" "$stage" OK "$dt"
  else
    warn "$card ${mode:+/$mode} :: $stage FAILED rc=$rc (${dt}s) -- see $STAGE_DIR/stage.log"
    record "$card" "$mode" "$stage" "FAIL_$rc" "$dt"
    [ "$KEEP_GOING" = "1" ] || die "aborting (--stop-on-error)"
  fi
  return 0
}

# ---------------------------------------------------------------------------
log "cards : ${CARDS[*]}"
log "modes : ${MODES[*]}"
log "stages: ${SEL_STAGES[*]}"

for card in "${CARDS[@]}"; do
  mkdir -p "$OUTDIR/$card"
  for stage in "${SEL_STAGES[@]}"; do
    if [[ "$MODE_INDEPENDENT" == *" $stage "* ]]; then
      run_stage "$card" "" "$stage"
    else
      for mode in "${MODES[@]}"; do
        run_stage "$card" "$mode" "$stage"
      done
    fi
  done
done

# ------------------------------------------------------------ summary -------
log "=== building summary page ==="
if [ "${DRY_RUN:-0}" != "1" ]; then
  python3 "$HERE/python/make_summary.py" \
      --outdir "$OUTDIR" --wwwdir "$WWWDIR" \
      --cards "${CARDS[@]}" --modes "${MODES[@]}" --include-known \
    && ok "summary: $WWWDIR/index.html" \
    || warn "summary page failed"
fi

printf '\n'
log "status table: $STATUS_FILE"
if [ "${DRY_RUN:-0}" != "1" ]; then
  n=$(awk -F'\t' 'NR>1 && $4!="OK" {print "  " $1" "$2" "$3" -> "$4}' \
        "$STATUS_FILE" | tee /dev/stderr | wc -l)
  [ "$n" = "0" ] && ok "every stage of this run finished successfully"
fi
log "web area: $WWWDIR"
case "$WWWDIR" in
  */www/*) log "        url: https://${USER}.web.cern.ch/${WWWDIR#*/www/}/" ;;
esac
