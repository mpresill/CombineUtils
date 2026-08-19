# ============================================================================
#  config.sh -- everything you are expected to edit lives here.
#  Sourced by run_diagnostics.sh; every variable can also be overridden from
#  the environment (VAR=... ./run_diagnostics.sh ...).
# ============================================================================

# ---------------------------------------------------------------- inputs ----
# Directory holding one sub-directory per category, each with a datacard.
CARD_DIR="${CARD_DIR:-/afs/cern.ch/work/j/jinw/public/VBSfit/cards/merged_offset_cat_v8_merged}"
# Sub-directories to process (order matters only for the summary page).
CARDS=(${CARDS:-boosted_e boosted_mu resolved_e resolved_mu combined})
# Datacard file name inside each sub-directory.
CARD_FILE="${CARD_FILE:-datacard.txt}"

# ------------------------------------------------------------ CMSSW/env ----
CMSSW_DIR="${CMSSW_DIR:-/afs/cern.ch/work/m/mpresill/combinev10/CMSSW_14_1_0_pre4}"

# --------------------------------------------------------------- outputs ----
# Scratch area for workspaces / combine output (large, not web exposed).
OUTDIR="${OUTDIR:-/afs/cern.ch/work/m/mpresill/combinev10/diagnostics/wv-run3}"
# Web area. An index.php is dropped in every sub-directory it creates.
WWWDIR="${WWWDIR:-/eos/user/m/mpresill/www/VBS/wv-run3}"
# index.php to replicate into every plot directory (leave empty to skip).
WWW_INDEX_PHP="${WWW_INDEX_PHP:-/eos/user/m/mpresill/www/VBS/index.php}"

# ---------------------------------------------------------------- physics ---
MASS="${MASS:-125}"                 # -m, only a label here (no mass scan)
POI="${POI:-r}"
EXPECT_SIGNAL="${EXPECT_SIGNAL:-1}" # signal strength injected in the Asimov
R_MIN="${R_MIN:--10}"
R_MAX="${R_MAX:-10}"

# The analysis is blind: the SR "data_obs" is MC, only the CRs hold real data.
# Every stage therefore runs on an Asimov dataset, in two flavours:
#   asimov      -t -1                     nuisances at their pre-fit values
#   asimovFreq  -t -1 --toysFrequentist   nuisances at their post-fit-to-data
#                                         values (a "post-fit Asimov")
# Set to a subset to run only one of them.
MODES=(${MODES:-asimov asimovFreq})

toy_opts_for_mode() {
  case "$1" in
    asimov)     echo "-t -1" ;;
    asimovFreq) echo "-t -1 --toysFrequentist" ;;
    observed)   echo "" ;;   # DO NOT USE while blind
    *) echo "unknown mode '$1'" >&2; return 1 ;;
  esac
}

# -------------------------------------------------------- minimiser opts ----
# Kept in one place so every stage uses an identical, reproducible setup.
MINIMIZER_OPTS="${MINIMIZER_OPTS:---cminDefaultMinimizerStrategy 0 --cminFallbackAlgo Minuit2,Migrad,0:0.2 --X-rtd MINIMIZER_MaxCalls=9999999 --X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NEVER_GIVE_UP --X-rtd FITTER_BOUND}"
ROBUST_OPTS="${ROBUST_OPTS:---robustFit=1 --setRobustFitTolerance 0.2 --stepSize=0.001}"

# How to recognise the free rate parameters and the autoMCStats parameters.
# These are resolved to explicit parameter names against the workspace (see
# resolve_parameter_sets in lib/common.sh) rather than passed to combine as
# rgx{...}: combine expands rgx{} against the nuisance set only, so freezing an
# unconstrained rateParam that way silently does nothing.
RATE_PARAM_REGEX="${RATE_PARAM_REGEX:-^norm_}"
MCSTAT_REGEX="${MCSTAT_REGEX:-^prop_bin}"

# Bounds applied to each free rate parameter. The cards declare them [0,5];
# keeping the lower bound off zero avoids a fit that parks a background at
# nothing, which is where the minimiser gets stuck.
RATEPARAM_MIN="${RATEPARAM_MIN:-0.1}"
RATEPARAM_MAX="${RATEPARAM_MAX:-5}"

# Random seed. Fixed so file names and results are reproducible.
SEED="${SEED:-123456}"

# Share one generated Asimov dataset between all stages (GenerateOnly --saveToys
# + --toysFile) instead of letting each combine call build its own from `-t -1`.
# On (1) the uncertainty breakdown, the impacts and the scan are all fits to the
# byte-identical dataset, which is what makes them comparable. On (0) every call
# just gets plain `-t -1`, exactly as the original scripts did -- one moving part
# fewer if you are chasing a problem.
USE_SHARED_TOYS="${USE_SHARED_TOYS:-1}"

# ------------------------------------------------------ nuisance groups -----
# Used for the uncertainty breakdown (stage: breakdown) and for the grouped
# impact summary. Format: "label:regex". The regex is handed to combine's
# rgx{} matcher, so it must match the FULL parameter name.
# Order = order in the breakdown table.
NUISANCE_GROUPS=(
  "JES_JER:AK(4|8)PFPuppi_(JER|JES_Total)"
  "btag:sf_btag_.*"
  "leptons:(sf_(ele|mu)_.*|ele_(scale|smear)|muon_(scale|smear))"
  "fakes:(electron|muon)_inverttight_to_fake_.*"
  "V_tagging:sf_(tau21|WvsQCD|qvg)_.*"
  "theory:(LHEPdfWeight_.*|LHEScaleWeight_.*|sf_partonshower_.*)"
  "pileup_lumi:(pileup|lumi_.*)"
  "bkg_norm:norm_.*"
  "MC_stat:prop_bin.*"
)

# ------------------------------------------------------------- resources ----
NCORES="${NCORES:-8}"                    # --parallel for combineTool
IMPACTS_JOB_MODE="${IMPACTS_JOB_MODE:-interactive}"   # interactive | condor
CONDOR_QUEUE="${CONDOR_QUEUE:-workday}"  # espresso/microcentury/longlunch/workday/tomorrow
GOF_NTOYS="${GOF_NTOYS:-300}"
GOF_ALGOS=(${GOF_ALGOS:-saturated KS AD})
SCAN_POINTS="${SCAN_POINTS:-61}"

# ----------------------------------------------------------- scans etc. -----
# Range scanned for the POI. R_MIN/R_MAX are the *fit* bounds and are wide on
# purpose; scanning that wide just wastes points.
SCAN_RANGE="${SCAN_RANGE:--1,3}"

# Control regions are identified by their channel-name suffix. Used to mask the
# signal regions for the control-region-only checks, which are blind-safe
# because those bins already hold real data.
CR_SUFFIX_REGEX="${CR_SUFFIX_REGEX:-_(TTCR|WCR)$}"

# Process grouping for the pre/post-fit plots.
PROCESS_GROUPS="${PROCESS_GROUPS:-$HERE/process_groups.json}"

# ------------------------------------------------------------- extras -------
# ChannelCompatibilityCheck groups: combine's -g takes a substring, and every
# channel containing it joins that group with its own signal strength. These
# match the four analysis categories, so each group covers one SR plus its two
# control regions. Only run when at least two of them are present.
CCC_GROUPS=(${CCC_GROUPS:-boosted_mu boosted_e resolved_mu resolved_e})

# FastScan over 150+ parameters is slow and mostly uninteresting; restrict it to
# the parameters that can actually matter.
FASTSCAN_MATCH="${FASTSCAN_MATCH:-^(r|norm_.*|prop_bin.*|AK[48]PFPuppi_.*|sf_btag_cferr.*|sf_qvg_.*|sf_tau21_.*|LHEScaleWeight_.*|pileup|.*inverttight.*)$}"
