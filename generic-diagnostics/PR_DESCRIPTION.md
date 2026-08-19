Rework of `generic-diagnostics/` so it runs on `/afs/cern.ch/work/j/jinw/public/VBSfit/cards/merged_offset_cat_v8_merged/*/datacard.txt` (all 5 cards) and publishes to `/eos/user/m/mpresill/www/VBS/wv-run3`.

Nothing has been run for real yet beyond validating the code — this is the review pass before the production run.

## How to use it

```bash
cd generic-diagnostics
./run_diagnostics.sh --list                      # stages and what each checks
./run_diagnostics.sh -n                          # print every command, run nothing
./run_diagnostics.sh -c boosted_e -s validate,workspace,significance
./run_diagnostics.sh                             # all cards, all stages, both modes
NCORES=16 ./run_diagnostics.sh -c combined -s impacts --condor
```

Everything editable is in `config.sh`; every variable can also be overridden from the environment. The old scripts are kept verbatim under `legacy/`.

## The two blind modes

| mode | options | nuisances at | what it tests |
|---|---|---|---|
| `asimov` | `-t -1` | pre-fit values | the machinery. Every pull must be exactly zero; a non-zero pull is a bug. |
| `asimovFreq` | `-t -1 --toysFrequentist` | post-fit-to-data values | the same checks around a realistic point; the pulls now show what the control-region data want. |

The Asimov dataset is generated **once** per (card, mode) with `GenerateOnly --saveToys` and handed to every later call via `--toysFile ... -t -1`. That is what makes the uncertainty breakdown and the impacts comparable — they are fits to literally the same dataset. Verified identical to passing `-t -1` directly (`Significance: 2.59085` both ways).

## Stages

`validate` · `workspace` · `significance` · `limits` · `fitdiag` · `nuisances` · `prepostfit` · `scan` · `breakdown` · `crfit` · `impacts` · `gof` · `extras`, then a summary `index.html` with one row per card and mode.

New relative to the old scripts: datacard/template validation, the workspace dump, pull and constraint plots with pathologies flagged, the correlation matrix, pre/post-fit plots, the likelihood scan with a stat-only overlay, the uncertainty breakdown by group, the control-region fit to data, goodness of fit, channel compatibility, FastScan, and minimiser stability. Plus resumable stages, per-stage logs, a `status.tsv`, and `--dry-run`.

## Silent-failure fixes worth reviewing

These are the ones that would have produced wrong numbers that look fine. All are commented in place and collected in the README.

- **`--freezeParameters rgx{}` does not match rateParams.** combine expands `rgx{}` against the nuisance set, and `text2workspace.py` does not put rateParams there, so it freezes nothing without warning. On `boosted_e` this reported the background-normalisation contribution as exactly `0.0000` — while `norm_top` is in fact the **second largest** contribution to `sigma_r` (0.29 of 0.57). Every parameter set is now resolved to explicit names against the workspace.
- **`combineTool -M Impacts` skips rateParams** for the same reason; they are now passed with `--named`.
- **`--robustFit` cannot find the 68% crossings when everything else is frozen** and silently reports the distance to the edge of the `r` range. That is exactly what a stat-only fit is. The breakdown uses MINOS (agrees with robustFit to <1% on the total fit) and rejects any error landing on the range edge.
- **`--floatParameters` does not override an earlier `--freezeParameters`**, so the "stat + MC stat" list is built explicitly.
- **combineTool strips quoting before `sh -c`**, so no regex metacharacters are handed to it.
- **CombineHarvester prepends the card directory to absolute shape paths**, so `ValidateDatacards.py` cannot read these cards; `localize_card.py` works around it.
- The rateParam bounds are now `0.1–5`, matching the `[0,5]` the cards declare. `all_the_things.sh` set `-2,4`, i.e. a negative lower bound on a parameter that cannot go below zero.

## Goodness of fit is reported as vacuous, not as a p-value

Worth a look before the run, because it is a real limitation rather than a bug:

- in the signal regions `data_obs` is **pseudo-data generated from the card's own templates** while blind — the prediction with the signal at r = 1 and the rate parameters at their control-region values. A least-squares fit of the `boosted_e` templates to their own `data_obs` returns r = 1.0006, norm_top = 0.7642, norm_wjet = 0.9025 with per-bin residuals of 0.03%. The model has exactly the freedom needed to reproduce it, so the statistic is ~0 and p = 1 by construction;
- masking the signal regions does not help: each control region is a single bin with its own free rate parameter, so the control regions are exactly saturated (zero d.o.f.).

The stage runs, detects this, and labels the result `VACUOUS` instead of printing a p-value that looks like good news. The commands are unchanged and give real numbers after unblinding. Until then the data check is the new `crfit` stage.

## Validation so far

`boosted_e` was run end to end in the `asimov` mode. Everything converged (`fit_status 0`, `covQual 3`) and the two independent uncertainty breakdowns agree:

| | total | stat | syst |
|---|---|---|---|
| from the two likelihood scans | 0.571 | 0.359 | 0.444 |
| from `--algo singles` with frozen groups | 0.573 | 0.360 | 0.446 |

Expected significance 2.59 sigma, `r = 1.000 +0.66/-0.48`, all `asimov` pulls exactly zero. Dominant systematic group: b tagging (53%), then background normalisation (51%), theory (30%), MC stat (27%). The template audit flags 33 systematics as prunable in this category and `ValidateDatacards.py` independently finds the same 33 with identical Up/Down templates. `crfit` gives `norm_top_boosted_e = 0.76 +/- 0.17` from control-region data alone.

Runtime, single-category card: `fitdiag` ~10 min (it is `--saveWithUncertainties` throwing 200 toys per channel), `extras` ~4 min, `breakdown` ~2 min, `scan` ~1 min. The `combined` card has 12 channels and will be several times slower; `impacts` there wants `--condor`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

## Review follow-ups (Copilot, PR #1)

All 16 comments addressed. The substantive ones:

| # | Defect | Fix |
|---|--------|-----|
| 1 | The `status.tsv` header was scanned as a failed stage, so a clean first run always reported one failure | take `RUN_START_LINE` *after* writing the header |
| 2 | A value option given as the last argument (`--cards`) left `$2` unset, `shift 2` failed, and the parse loop spun forever | `need_arg` guard on every option that takes a value |
| 4 | On `--condor` the stage submitted and returned every time, so `impacts*.json` was never produced | count the per-parameter fit outputs and collect once they are all present |
| 5 | The "a grid point found a better minimum" check could never fire — the curve was shifted to zero before it ran | record the raw minimum before shifting |
| 6 | `--channel-masks` puts floating `mask_*` vars in the workspace; the dump reported each as a free parameter *and* as sitting on its boundary | exclude `mask_*`, as `list_params.py` already did |
| 7 | Channel compatibility used the error pointing *away* from the combined value, misreporting every n-sigma | a group below the combination travels up, so use the up error |
| 8 | Vacuity was tested as `obs < min(toys)`: it missed the all-zero case (says `vacuous: false`) and flagged good fits, which land there 1/(N+1) of the time | test the statistic itself — numerically zero, zero toy spread, or orders of magnitude below the toy median |
| 9 | The parameter-set cache keyed on the workspace timestamp only, so changing `RATE_PARAM_REGEX` or the rateParam bounds silently reused the old lists | signature line covering all four inputs |
| 10 | `shape <scale>` entries were audited on the full template excursion, not the scaled one combine actually applies | apply `scale` before ranking (the negative-bin check stays on the raw template) |
| 13 | `plot_scan.py` writes `scan_summary*.json`; the stage published `scan*.json`, so the machine-readable result never reached the web area | fixed the name |
| 14 | Two `shapes` lines with the same file name in different directories collided on one symlink, silently validating the wrong templates | disambiguate with a path hash |
| 16 | `gof` reads neither `MODE` nor `DATA_OPTS`, but ran once per mode, producing two differently fluctuated p-values presented as mode-specific | moved to `MODE_INDEPENDENT` |

3, 11, 12 and 15 were smaller: dropped exit statuses on the inline report generators, a missing datacard bypassing `--stop-on-error`, and `--dry-run` doing real work. A dry run of one card now prints 59 commands with no stage failures and no side effects beyond `mkdir`.

Verified after the changes: `validate` + `workspace` on `boosted_e` reproduce the earlier numbers (33 prunable systematics, 153 nuisances, 12 autoMCStats), the workspace dump now lists 2 free parameters instead of 5 and no boundary parameters, the scan health check fires on a synthetic curve with a negative point, and the GoF summariser separates all-zero, below-all-toys, and ordinary p-values correctly.
