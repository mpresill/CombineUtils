# WV Run-3 VBS — Combine diagnostics slides

`wv_run3_diagnostics.md` is a [Marp](https://marp.app) deck, 10 slides, 16:9,
in Texas Tech scarlet (`#CC0000`) on white.

---

## Building it on lxplus

lxplus has two quirks that stop Marp working out of the box, and both are
handled for you:

1. **No Chrome/Chromium.** Marp renders PDF/PPTX/PNG through a headless
   browser; lxplus9 ships only Firefox, which Marp cannot drive. Fixed by a
   rootless `chrome-headless-shell` (see below).
2. **npm's cache defaults into AFS**, where it dies with
   `EXDEV: cross-device link not permitted`. Fixed by putting the cache on
   local scratch.

### The short version

```bash
cd slides/wv-run3
./make.sh          # -> wv_run3_diagnostics.pdf
./make.sh html     # -> wv_run3_diagnostics.html (no browser needed)
./make.sh pptx     # -> editable PowerPoint
```

`make.sh` sets `CHROME_PATH` and `npm_config_cache` for you and passes the two
flags the deck needs: `--html` (the two-column layout is built from `<div>`s,
which Marp strips otherwise) and `--allow-local-files` (the figures come off
the local filesystem).

Verified on lxplus9, el9, Aug 2026 — 10 pages, 960×540 pt.

### Installing chrome-headless-shell (once, ~261 MB)

Already installed under `/afs/cern.ch/work/m/mpresill/tools/`. To redo it, or
to put it somewhere else:

```bash
mkdir -p ~/work/tools && cd ~/work/tools
V=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["channels"]["Stable"]["version"])')
curl -sLO https://storage.googleapis.com/chrome-for-testing-public/$V/linux64/chrome-headless-shell-linux64.zip
unzip -q chrome-headless-shell-linux64.zip && rm chrome-headless-shell-linux64.zip
./chrome-headless-shell-linux64/chrome-headless-shell --version   # should print a version
```

Then either edit the default in `make.sh`, or export `CHROME_PATH` yourself.
Put it in **work** or **eos**, not your AFS home — the home quota is far too
small for it.

---

## Editing it in VS Code (Remote-SSH to lxplus)

1. Connect with **Remote-SSH** and open the `CombineUtils` folder.
2. Install **Marp for VS Code** (`marp-team.marp-vscode`) — when prompted,
   choose **Install in SSH: lxplus**, not locally. Extensions that touch
   workspace files run on the remote.
3. Open `wv_run3_diagnostics.md` and click the preview icon (or
   `Ctrl+K V`). The preview renders inside VS Code and needs no browser, so it
   works immediately.
4. Export: command palette → **"Marp: Export slide deck..."**.

The repo ships a `.vscode/settings.json` that turns on `markdown.marp.html`
(without it the `<div>`s show up as literal text in the slides) and points
`markdown.marp.chromePath` at the headless shell. If your Marp version does not
have the `chromePath` setting, either export with `./make.sh` instead — that
path is the one actually tested here — or launch VS Code with `CHROME_PATH`
already set in the environment.

---

## Figures

`figs/*.png` are trimmed 150-dpi rasterisations of the PDFs published under
`/eos/user/m/mpresill/www/VBS/wv-run3/`:

```bash
pdftoppm -png -r 150 -f 1 -l 1 -singlefile <in>.pdf figs/<out>
convert figs/<out>.png -trim +repage -bordercolor white -border 12 figs/<out>.png
```

Regenerate them from the web area after a new run; the file names used by the
deck are stable, so nothing in the markdown needs to change.

## Colours

Texas Tech scarlet `#CC0000` on white, `#63666A` grey for secondary text,
`#F2F2F2` for callout backgrounds. Defined once as CSS variables in the
`style:` block of the front matter — change them there and the whole deck
follows.
