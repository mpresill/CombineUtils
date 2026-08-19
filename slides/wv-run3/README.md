# WV Run-3 VBS — Combine diagnostics slides

`wv_run3_diagnostics.md` is a [Marp](https://marp.app) deck (10 slides, 16:9).

## Viewing / exporting in VS Code

Install the **Marp for VS Code** extension (`marp-team.marp-vscode`), open the
file, and hit the preview button. Export with the Marp command palette entry
*"Export slide deck..."* → PDF / PPTX / HTML.

From the command line:

```bash
npx @marp-team/marp-cli@3 wv_run3_diagnostics.md -o wv_run3_diagnostics.pdf   # needs Chrome/Chromium
npx @marp-team/marp-cli@3 wv_run3_diagnostics.md -o wv_run3_diagnostics.html  # no browser needed
```

## Figures

`figs/*.png` are trimmed 150-dpi rasterisations of the PDFs published under
`/eos/user/m/mpresill/www/VBS/wv-run3/`, produced with:

```bash
pdftoppm -png -r 150 -f 1 -l 1 -singlefile <in>.pdf figs/<out>
convert figs/<out>.png -trim +repage -bordercolor white -border 12 figs/<out>.png
```

Regenerate them from the web area after a new run; the file names in the deck
are stable.

## Colours

Texas Tech scarlet `#CC0000` on white, with `#63666A` grey for secondary text.
Defined once in the `style:` block of the front matter.
