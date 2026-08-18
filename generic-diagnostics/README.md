# generic-diagnostics

Blind combine diagnostics for the WV run-3 VBS fit, driven by one script over a
list of datacards.

```bash
cd generic-diagnostics
./run_diagnostics.sh --list                      # what it can do
./run_diagnostics.sh -n                          # print every command, run nothing
./run_diagnostics.sh -c boosted_e -s validate,workspace,significance
./run_diagnostics.sh                             # all cards, all stages, both modes
```

Configuration is in **`config.sh`** and nothing else needs editing. Every
variable there can also be overridden from the environment:

```bash
NCORES=16 MODES=asimov ./run_diagnostics.sh -c combined -s impacts --condor
```

## Why two modes

The analysis is blind, so no stage ever fits the observed dataset in the signal
regions. Each check runs on an Asimov dataset built in one of two ways:

| mode | combine options | nuisances set to | what it tests |
|---|---|---|---|
| `asimov` | `-t -1` | their pre-fit values | the machinery. **Every pull must come back exactly zero** — a non-zero pull here is a bug, not physics. |
| `asimovFreq` | `-t -1 --toysFrequentist` | their post-fit-to-data values | the same checks around a realistic point: the pulls now show what the data want. |

One caveat that is specific to these cards, and which the reports repeat: the
signal-region `data_obs` is **MC**, only the two control regions per category
(`*_TTCR`, `*_WCR`) hold real data. So `--toysFrequentist` is "post-fit to the
control regions", and any goodness-of-fit statement about real data has to come
from the control-region-only variant.

The Asimov dataset is generated **once** per (card, mode) with
`GenerateOnly --saveToys` and then passed to every subsequent call via
`--toysFile ... -t -1`. That is what makes the uncertainty breakdown and the
impacts comparable to each other — they are all fits to literally the same
dataset.

## Stages

Run in this order; `-s` takes any subset.

| stage | what it produces |
|---|---|
| `validate` | `ValidateDatacards.py`, the `systematicsAnalyzer.py` nuisance table, and `audit_shapes.py` — a per-template audit of the input histograms |
| `workspace` | `text2workspace.py` (with `--channel-masks`) plus a dump of the POI, the constrained nuisances, the **free** rateParams and their ranges, and the autoMCStats parameters |
| `significance` | expected significance and local p-value |
| `limits` | `AsymptoticLimits`, background-only (`--run blind`) and signal-injected |
| `fitdiag` | one `FitDiagnostics` call giving both the b-only and s+b fits, with shapes and normalisations saved |
| `nuisances` | `diffNuisances.py`, a pull/constraint plot, the correlation matrix, post-fit normalisations |
| `prepostfit` | pre-fit and post-fit distributions per channel with uncertainty bands |
| `scan` | profile likelihood scan of `r`, total and stat-only, with the intervals read off the crossings |
| `breakdown` | uncertainty contribution of each nuisance group, by freezing groups at their post-fit values |
| `crfit` | **the only stage that touches observed data**, and blind-safe: the signal regions are masked out with `mask_*` and the top / W+jets rate parameters are fitted to the control regions alone |
| `impacts` | per-nuisance impacts and the ranked plot, rate parameters included |
| `gof` | goodness of fit against toys, control-region-only and all-channels |
| `extras` | `ChannelCompatibilityCheck`, `FastScan`, and minimiser stability |

Then `python/make_summary.py` writes `index.html` in the web area with one row
per card and mode. It only reads files, so it is safe to re-run while jobs are
still going.

## What was added relative to the old scripts

`legacy/all_the_things.sh` and `legacy/do_impacts.sh` are kept for reference.
They did the significance, one `FitDiagnostics`, `diffNuisances` and the
impacts, with hard-coded paths and no error checking. New here:

* **`ValidateDatacards.py`** and a **template audit** — run before any fit.
  The audit ranks every shape systematic by the largest change it makes to any
  single bin of the total expectation, which is the number that decides whether
  a systematic matters, and flags missing variations, negative bins, one-sided
  variations and systematics that are negligible everywhere (prunable).
* **A workspace dump** that shows which parameters are unconstrained. An
  unbounded rateParam is the most common cause of a fit that wanders off, and
  the old script's `'rgx{.*norm_.*}'=-2,4` set a *negative* lower bound on
  parameters the card declares as `[0,5]`.
* **Pull and constraint plots** with the pathologies called out: `|pull| > 1`,
  over-constrained (`sigma_post/sigma_pre < 0.5`) and inflated (`> 1.05`).
* **Correlation matrix** and the list of parameters most correlated with `r`,
  plus pairs above `|rho| = 0.8` as degeneracy candidates.
* **Pre-fit and post-fit plots** per channel, from the saved shapes.
* **Likelihood scan** with a stat-only overlay, and a check that the curve is
  actually well behaved (monotonic, minimum not at the edge).
* **Uncertainty breakdown** by nuisance group, using the best-fit snapshot so
  that frozen means "frozen at the post-fit value".
* **Goodness of fit**, including a control-region-only variant that is a
  genuine test against real data while blind.
* **ChannelCompatibilityCheck** — on an Asimov every category must return the
  injected signal strength.
* **FastScan** — the fastest way to find a template that makes the likelihood
  non-smooth.
* **Minimiser stability** — the same fit with three minimiser configurations;
  if they disagree, nothing downstream is trustworthy.
* One dataset shared by every stage, a status table, `--dry-run`, resumable
  stages (`FORCE=1` to redo), and per-stage logs.

## Combine traps this suite works around

These are all things that fail *silently*. They were found while getting the
suite to run on these cards, and each one is commented at the place it matters.

**`--freezeParameters rgx{...}` does not match rateParams.** combine expands the
`rgx{}` shorthand against the nuisance-parameter set, and `text2workspace.py`
does not put rateParams there. So `--freezeParameters rgx{norm_.*}` runs without
a warning and freezes nothing. On `boosted_e` that turned the background
normalisation line of the uncertainty breakdown into exactly `0.0000` — while
`norm_top` is in fact the *second largest* contribution to the uncertainty on
`r` (0.29 of 0.57). Every parameter set is therefore resolved to explicit names
against the workspace first (`lib/common.sh: resolve_parameter_sets`,
`python/list_params.py`), which also makes a group whose regex matches nothing an
explicit warning instead of a zero.

**rateParams are missing from the impacts ranking by default**, for the same
reason: `combineTool.py -M Impacts` takes its list from the workspace's nuisance
set. The impacts stage passes `--named <nuisances>,<rate params>` explicitly.

**`--robustFit=1` cannot find the 68% crossings when everything else is frozen.**
It reports the distance to the edge of the `r` range instead, which looks like a
large but valid uncertainty. That is what a stat-only fit is, so the breakdown
stage uses MINOS throughout. On the total fit the two agree to under 1%
(`-0.484/+0.663` vs `-0.478/+0.655`), and `make_breakdown.py` rejects any
uncertainty that lands on the range edge.

**`--floatParameters` does not override an earlier `--freezeParameters`.** The
"stat + MC stat" line cannot be built by freezing everything and re-floating
`prop_bin*`; both lists are constructed explicitly.

**combineTool.py strips quoting.** It rebuilds the combine command line and runs
it through `sh -c`, so anything containing `(`, `|` or `{}` dies with a shell
syntax error inside the impacts stage. The rate-parameter ranges are spelled out
by name there rather than passed as `rgx{...}`.

**CombineHarvester cannot read these cards directly.** `ParseDatacard` prepends
the datacard's directory to the shape file name even when it is already
absolute. `python/localize_card.py` writes a copy with local names plus a symlink
so `ValidateDatacards.py` works.

**combine appends the random seed to output file names only when it generates
toys.** With `--toysFile` it does not, which is what lets `-M Impacts` find its
own initial-fit file. Everything that looks up a combine output still globs
(`combine_out` in `lib/common.sh`) rather than assuming a name.

## Notes and gotchas

* **Goodness of fit cannot say anything yet.** In the signal regions `data_obs`
  is the MC prediction itself while blind, so the model fits it perfectly and
  the p-value comes out at 1 by construction. Masking the signal regions does
  not help either: each control region is a single bin with its own free rate
  parameter, so the control regions are exactly saturated (zero degrees of
  freedom). The stage detects this and labels the results VACUOUS instead of
  printing a p-value that looks like good news. Re-run it unchanged after
  unblinding. Until then the data check is the `crfit` stage.
* **Runtime.** `fitdiag` is the slowest single call: ~10 min on a
  single-category card, because `--saveWithUncertainties` throws 200 toys per
  channel for the per-bin uncertainties. `breakdown` is ~2 min (one fit per
  group), `extras` ~4 min, `scan` ~1 min. The `combined` card has 12 channels
  and will be several times slower everywhere; `impacts` there is one fit per
  parameter and wants `--condor`.
* **Cross-flavour systematics look prunable in a single-flavour card.** The
  template audit reports every `muon_*` systematic as negligible in
  `boosted_e`. That is correct and expected; judge pruning on the `combined`
  card.
* `prop_bin*_TTCR_bin0` and friends are the autoMCStats parameters of
  single-bin control regions. They are constrained hard by construction
  (`sigma_post/sigma_pre = 0.42` on `boosted_e`), so a small value there is not
  a bug.
* **Two independent uncertainty breakdowns.** The `scan` stage gets the
  stat/syst split from two likelihood scans, the `breakdown` stage from
  `--algo singles` with frozen groups. They are computed completely differently
  and agree on `boosted_e` (total 0.571/0.573, stat 0.359/0.360, syst
  0.444/0.446). If they ever disagree, something is wrong.
* **Web area.** Plots go to `$WWWDIR/<card>/<mode>/<stage>/`, each with a copy
  of `index.php` so the CERN web server renders a gallery. The top level keeps
  `index.html` (the summary) and deliberately has no `index.php`.
* **`--condor`.** `impacts` submits and returns immediately. Watch with
  `condor_q -nobatch` and re-run the same command once the queue is empty to
  collect and plot.
* **Resuming.** Every stage drops a `.done` sentinel and is skipped on a re-run;
  `FORCE=1` or `-f` redoes it. `$OUTDIR/status.tsv` records every stage with its
  exit status and wall time.
