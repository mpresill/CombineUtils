# ---------------------------------------------------------------------------
# stage: breakdown -- how much of the uncertainty on the POI each group of
# nuisances is responsible for.
#
# Method (the standard combine recipe):
#   * start from the s+b best fit stored as a snapshot, so that a frozen
#     nuisance is frozen at its post-fit value and not at zero
#   * refit with MultiDimFit --algo singles, once with everything floating and
#     once per group with that group frozen
#   * the group's contribution is sqrt(sigma_total^2 - sigma_frozen^2)
#
# Also produced: the fully frozen fit ("stat only"), and "stat + MC stat" which
# is the usual second line of the table.
#
# Groups are defined in config.sh (NUISANCE_GROUPS) as label:regex.
#
# These fits deliberately use MINOS rather than --robustFit. robustFit finds the
# 68% crossings by re-minimising the other parameters at each step, and when
# every other parameter is frozen it has nothing to minimise: it gives up and
# reports the distance to the edge of the r range, which silently turns the
# stat-only line into a nonsense number. MINOS handles all these fits, and on
# the total fit the two agree to better than 1% (-0.484/+0.663 vs
# -0.478/+0.655 on boosted_e), so nothing is lost by being consistent.
# ---------------------------------------------------------------------------
sentinel="$STAGE_DIR/.done"
already_done "$sentinel" && { log "breakdown already done"; return 0; }

ensure_toy_dataset || return 1
ensure_bestfit_snapshot || return 1
resolve_parameter_sets || return 1
cd "$STAGE_DIR" || return 1
rc=0

# ROBUST_OPTS matters here, not just for speed: without it the default crossing
# algorithm gives up on one side of the interval on the harder (post-fit Asimov)
# datasets -- "No valid low-error found, will report difference to minimum of
# range" -- and combine then reports the distance to R_MIN as the error, which
# silently turns one row of the breakdown into nonsense. It also keeps these
# fits consistent with the best-fit snapshot they start from, which is built
# with the same options.
singles() {  # <tag> [<comma separated parameters to freeze>]
  local tag="$1" freeze="${2:-}"
  runs "combine -M MultiDimFit -d '$SNAPSHOT_WS' -w w --snapshotName MultiDimFit \
        -m $MASS -n '$tag' --algo singles $DATA_OPTS -P $POI --floatOtherPOIs 1 \
        --setParameterRanges ${POI}=${R_MIN},${R_MAX}${RATE_RANGES:+:$RATE_RANGES} \
        $MINIMIZER_OPTS $ROBUST_OPTS \
        ${freeze:+--freezeParameters '$freeze'} \
        > 'fit${tag}.log' 2>&1"
}

declare -a bd_labels bd_files

singles "_bd_total${TAG}" "" || { warn "total fit failed"; rc=1; }
bd_labels+=("total"); bd_files+=("$(combine_out "$STAGE_DIR" "_bd_total${TAG}" MultiDimFit)")

# One group at a time. The group regex is resolved to explicit parameter names
# first: combine expands rgx{} against the nuisance set only, so a group that
# contains rate parameters would otherwise be frozen silently not at all and
# report a contribution of exactly zero.
for label in $(group_labels); do
  rx="$(group_regex "$label")"
  safe="$(echo "$label" | tr -c 'A-Za-z0-9_' '_' | sed 's/_*$//')"
  members="$(group_params "$rx")"
  if [ -z "$members" ]; then
    warn "group '$label' (regex '$rx') matches no parameter in this workspace -- skipped"
    continue
  fi
  log "group $label: $(count_csv "$members") parameter(s)"
  if singles "_bd_${safe}${TAG}" "$members"; then
    bd_labels+=("$label")
    bd_files+=("$(combine_out "$STAGE_DIR" "_bd_${safe}${TAG}" MultiDimFit)")
  else
    warn "breakdown fit for group '$label' failed"
    rc=1
  fi
done

# Reference points: everything frozen, and everything except the autoMCStats
# parameters frozen (the usual second line of an uncertainty table). Note that
# --floatParameters cannot be used to carve out a subset here: it does not
# override an earlier --freezeParameters, so the two lists are built explicitly.
if singles "_bd_statonly${TAG}" "$STAT_ONLY_LIST"; then
  bd_labels+=("__stat_only__")
  bd_files+=("$(combine_out "$STAGE_DIR" "_bd_statonly${TAG}" MultiDimFit)")
else
  warn "stat-only fit failed"; rc=1
fi
if [ -n "$MCSTAT_PARAMS" ]; then
  if singles "_bd_statmc${TAG}" "$STAT_PLUS_MCSTAT_LIST"; then
    bd_labels+=("__stat_plus_mcstat__")
    bd_files+=("$(combine_out "$STAGE_DIR" "_bd_statmc${TAG}" MultiDimFit)")
  else
    warn "stat+MCstat fit failed"; rc=1
  fi
fi

runs "python3 '$HERE/python/make_breakdown.py' --poi $POI \
        --title '$CARD / $MODE' \
        --output-prefix 'breakdown${TAG}' --rmin $R_MIN --rmax $R_MAX \
        --report 'breakdown${TAG}.txt' --json 'breakdown${TAG}.json' \
        $(for i in "${!bd_labels[@]}"; do
             [ -n "${bd_files[$i]}" ] && printf -- "--entry '%s=%s' " "${bd_labels[$i]}" "${bd_files[$i]}"
          done)" \
  || { warn "make_breakdown.py failed"; rc=1; }

publish "$STAGE_DIR/breakdown${TAG}.txt" "$STAGE_DIR/breakdown${TAG}.json"
for f in "$STAGE_DIR"/*.png "$STAGE_DIR"/*.pdf; do [ -e "$f" ] && publish "$f"; done
[ "$rc" -eq 0 ] && mark_done "$sentinel"
return $rc
