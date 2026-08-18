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

- in the signal regions `data_obs` **is** the MC prediction while blind, so the model fits it perfectly (observed saturated statistic 0.0018 against toys of 4–15, p = 1 by construction);
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
