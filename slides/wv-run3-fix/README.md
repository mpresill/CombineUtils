# WV Run-3 VBS — combined-card diagnostics

`wv_run3_asimovfreq_fix.md` is a 5-slide Marp deck, same Texas Tech theme as
`../wv-run3/`, summarising the current combined-card `asimov` vs `asimovFreq`
results: the Results and Flagged-pathologies tables (same numbers as the
`combined` rows of the web summary page), the uncertainty breakdown by group
as text, and the nuisance-correlation-with-r plot for each mode. The
`asimovFreq` numbers here are the corrected ones (after fixing the missing
`--toysFrequentist` on the reading side in
`generic-diagnostics/lib/common.sh::ensure_toy_dataset`) and supersede the
`asimovFreq` numbers in `../wv-run3/wv_run3_diagnostics.md`.

## Building it

Same as `../wv-run3/`, with one extra gotcha:

```bash
cd slides/wv-run3-fix
./make.sh          # -> wv_run3_asimovfreq_fix.pdf
./make.sh html      # -> wv_run3_asimovfreq_fix.html
```

**If you build this from a shell that has `cmsenv` sourced**, Node's `zlib`
picks up cvmfs's `libz.so.1` off `LD_LIBRARY_PATH` instead of the system one,
and every `npm`/`npx` fetch or tar-extract fails with
`zlib: invalid distance too far back` — including installs from a local file,
so it is not a network issue. Fix: run the build with `LD_LIBRARY_PATH`
unset, e.g. `env -u LD_LIBRARY_PATH ./make.sh`, or build from a plain lxplus
shell that never sourced CMSSW.

## Figures

`figs/correlations_asimov.png` and `figs/correlations_asimovFreq.png` are
copied straight from `combined/{asimov,asimovFreq}/nuisances/correlations_combined_*_poi.png`
in the scratch area (`OUTDIR` in `generic-diagnostics/config.sh`) — the
"correlation with r" bar chart, not the full nuisance-nuisance matrix.
