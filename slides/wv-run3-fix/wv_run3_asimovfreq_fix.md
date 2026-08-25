---
marp: true
theme: default
paginate: true
size: 16:9
math: mathjax
footer: "M. Presilla"
style: |
  /* ---- Texas Tech HEP palette ---------------------------------------- */
  :root {
    --tt-scarlet: #CC0000;
    --tt-black:   #000000;
    --tt-grey:    #63666A;
    --tt-light:   #F2F2F2;
  }
  section {
    background: #FFFFFF;
    color: var(--tt-black);
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 22px;
    padding: 46px 54px 46px 54px;
  }
  section::after {           /* page number */
    color: var(--tt-grey);
    font-size: 14px;
  }
  h1 {
    color: var(--tt-scarlet);
    font-size: 40px;
    border-bottom: 4px solid var(--tt-scarlet);
    padding-bottom: 6px;
    margin-bottom: 14px;
  }
  h2 { color: var(--tt-black); font-size: 27px; margin: 10px 0 6px 0; }
  h3 { color: var(--tt-grey);  font-size: 21px; margin: 6px 0 4px 0; }
  strong { color: var(--tt-scarlet); }
  a { color: var(--tt-scarlet); }
  table { font-size: 19px; border-collapse: collapse; margin: 4px 0; }
  th {
    background: var(--tt-scarlet); color: #FFFFFF;
    font-weight: 600; padding: 4px 10px;
  }
  td { padding: 3px 10px; border-bottom: 1px solid #D8D8D8; }
  tr:nth-child(even) td { background: var(--tt-light); }
  code { background: var(--tt-light); color: var(--tt-black); font-size: 0.88em; }
  ul { margin: 4px 0; }
  li { margin: 2px 0; }
  footer {                   /* the tiny name on every slide */
    color: var(--tt-grey);
    font-size: 10px;
    opacity: 0.8;
  }
  .box {
    background: var(--tt-light);
    border-left: 5px solid var(--tt-scarlet);
    padding: 6px 14px; margin: 8px 0; font-size: 20px;
  }
  .box p { margin: 5px 0; }
  img { display: block; margin: 0 auto; }
  .small { font-size: 18px; }
  .tiny  { font-size: 15px; color: var(--tt-grey); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
  section.fig { padding: 22px 30px 30px 30px; }
  section.fig h1 { font-size: 30px; margin-bottom: 8px; padding-bottom: 4px; border-bottom-width: 3px; }
  section.title { background: var(--tt-black); color: #FFFFFF; }
  section.title h1 {
    color: #FFFFFF; border-bottom: 5px solid var(--tt-scarlet);
    font-size: 46px;
  }
  section.title h2 { color: var(--tt-scarlet); }
  section.title code { background: #2A2A2A; color: #FFFFFF; }
  section.title p  { color: #DCDCDC; }
---

<!-- _class: title -->
<!-- _paginate: false -->

# WV Run-3 VBS — combined-card diagnostics

## `asimov` vs `asimovFreq`, blind

Combine v10.0.2 — CMSSW_14_1_0_pre4

<span class="tiny">Full output: <code>/eos/user/m/mpresill/www/VBS/wv-run3</code> — code: <code>CombineUtils/generic-diagnostics</code></span>

---

# Results — combined

| mode | Z | p | $\hat r$ | $\sigma_{\rm tot}$ | $\sigma_{\rm stat}$ | $\sigma_{\rm syst}$ | dominant syst. | status | covQual |
|---|---|---|---|---|---|---|---|---|---|
| `asimov` | 3.747 | $8.9\times10^{-5}$ | $+1.0000$ | 0.4019 | 0.1905 | 0.3555 | btag | 0 | 2 |
| `asimovFreq` | 2.915 | $1.8\times10^{-3}$ | $+1.0002$ | 0.4828 | 0.2385 | 0.4198 | MC_stat | 0 | 3 |

<div class="box">

**Uncertainty breakdown by group** (no plot, numbers only — quadrature-sum totals, not stat-only-subtraction quoted above):

`asimov` — btag 55.1%, bkg_norm 55.0%, theory 41.8%, MC_stat 41.5%, V_tagging 40.4%, JES_JER 10.5%, fakes 7.6%, pileup_lumi 5.4%, leptons 5.0%

`asimovFreq` — MC_stat 49.5%, bkg_norm 46.4%, btag 45.7%, V_tagging 43.9%, theory 36.3%, JES_JER 27.7%, leptons 25.7%, fakes 16.3%, pileup_lumi 6.2%

</div>

---

# Flagged pathologies — combined

<span class="tiny">Counts, not verdicts — green means nothing was flagged.</span>

| mode | ident. Up/Down | one-sided | large lnN | tmpl errors | tmpl warnings | prunable | \|pull\|>1 | over-constr. | inflated |
|---|---|---|---|---|---|---|---|---|---|
| `asimov` | 46 | 32 | 25 | **0** | 149 | 12 | 7 | 0 | **0** |
| `asimovFreq` | 46 | 32 | 25 | **0** | 149 | 12 | 1 | 4 | — |

<div class="box">

`asimov` also reports **non-zero pull on Asimov = 0**, as required for a pre-fit Asimov (not applicable to `asimovFreq`). `minimiser stable` / `CCC p` / `GoF` are not populated per-mode on the summary page — see the `crfit`/`gof` stage pages directly.

</div>

---

<!-- _class: fig -->

# Nuisance correlation with $r$ — `asimov`

![h:565](figs/correlations_asimov.png)

---

<!-- _class: fig -->

# Nuisance correlation with $r$ — `asimovFreq`

![h:565](figs/correlations_asimovFreq.png)

<span class="tiny">Same leading rate parameters as `asimov`, plus `sf_btag_cferr1`/`sf_btag_lfstats2` rising once nuisances are fit to data.</span>

---

<!-- _class: fig -->

# Impacts — combined, `asimov` (page 1 of 6)

![h:565](figs/impacts_asimov_p1.png)

<span class="tiny">211/211 per-parameter fits usable. Pulls identically zero, as required for a pre-fit Asimov.</span>

---

<!-- _class: fig -->

# Impacts — combined, `asimovFreq` (page 1 of 6)

![h:565](figs/impacts_asimovFreq_p1.png)

<span class="tiny">211/211 fits usable. Pulls now non-zero — the ranking is built at the nuisance values the data prefers.</span>

---

# Impact summaries side by side

<div class="cols">
<div>

### `asimov`
![w:475](figs/impacts_asimov_summary.png)

</div>
<div>

### `asimovFreq`
![w:475](figs/impacts_asimovFreq_summary.png)

</div>
</div>

---

<!-- _class: fig -->

# Control-region fit to real data

![h:500](figs/crfit_combined.png)

<span class="tiny">`combine -M MultiDimFit --algo singles`, observed data, signal regions masked via `--setParameters mask_SR=1,...` and `r` frozen to 0 — the one stage here that touches real data, and only in the control regions.</span>
