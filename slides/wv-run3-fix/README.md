# WV Run-3 VBS — `asimovFreq` snapshot fix

`wv_run3_asimovfreq_fix.md` is a 7-slide Marp deck, same Texas Tech theme as
`../wv-run3/`, covering the corrected combined-card `asimovFreq` results after
fixing the missing `--toysFrequentist` on the reading side (see
`generic-diagnostics/lib/common.sh::ensure_toy_dataset`). It supersedes the
`asimovFreq` numbers in `../wv-run3/wv_run3_diagnostics.md` — the `asimov`
numbers there are unaffected and still stand.

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

`figs/*.png` are the same trim/rasterise recipe as `../wv-run3/`, pulled from
the Aug 24 2026 re-run under `/eos/user/m/mpresill/www/VBS/wv-run3/combined/asimovFreq/`.
The `_buggy` ones are copied straight from `../wv-run3/figs/` — the original,
pre-fix run — for the before/after comparison slides.
