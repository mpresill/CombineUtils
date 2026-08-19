#!/bin/bash
# Build the deck on lxplus. Verified working on lxplus9 (el9).
#
#   ./make.sh          -> wv_run3_diagnostics.pdf
#   ./make.sh html     -> wv_run3_diagnostics.html   (no browser needed)
#
# PDF/PPTX/PNG export needs a Chrome/Chromium, which lxplus does not ship.
# Point CHROME_PATH at one; the default below is a rootless chrome-headless-shell
# unpacked under ~/work/tools (see README for how to install it).
set -euo pipefail
cd "$(dirname "$0")"

: "${CHROME_PATH:=/afs/cern.ch/work/m/mpresill/tools/chrome-headless-shell-linux64/chrome-headless-shell}"
export CHROME_PATH

# npm's default cache in AFS breaks with "EXDEV: cross-device link not permitted";
# keep it on local scratch instead.
export npm_config_cache="${npm_config_cache:-/tmp/$USER/npmcache}"
mkdir -p "$npm_config_cache"

fmt="${1:-pdf}"
out="wv_run3_diagnostics.$fmt"

# --html      : the two-column layout is built from <div>s, which Marp drops otherwise
# --allow-local-files : figures are read from figs/ off the local filesystem
opts=(--html --allow-local-files)
if [ "$fmt" = html ]; then
  opts=(--html)          # a self-contained html inlines the figures already
fi

npx --yes @marp-team/marp-cli@3 wv_run3_diagnostics.md -o "$out" "${opts[@]}"
echo "wrote $PWD/$out"
