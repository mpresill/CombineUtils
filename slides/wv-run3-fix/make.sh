#!/bin/bash
# Build the deck on lxplus. See ../wv-run3/README.md for the full setup notes
# (chrome-headless-shell install, VS Code Marp extension, etc.) -- identical
# here, just pointed at this deck's markdown file.
#
#   ./make.sh          -> wv_run3_asimovfreq_fix.pdf
#   ./make.sh html     -> wv_run3_asimovfreq_fix.html   (no browser needed)
set -euo pipefail
cd "$(dirname "$0")"

: "${CHROME_PATH:=/afs/cern.ch/work/m/mpresill/tools/chrome-headless-shell-linux64/chrome-headless-shell}"
export CHROME_PATH

export npm_config_cache="${npm_config_cache:-/tmp/$USER/npmcache}"
mkdir -p "$npm_config_cache"

fmt="${1:-pdf}"
out="wv_run3_asimovfreq_fix.$fmt"

opts=(--html --allow-local-files)
if [ "$fmt" = html ]; then
  opts=(--html)
fi

npx --yes @marp-team/marp-cli@3 wv_run3_asimovfreq_fix.md -o "$out" "${opts[@]}"
echo "wrote $PWD/$out"
