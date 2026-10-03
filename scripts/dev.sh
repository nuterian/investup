#!/usr/bin/env bash
# Set up and run the Investup site locally.
#
#   INVESTUP_USER_AGENT="Your Name you@example.com" ./scripts/dev.sh
#
# First run downloads SEC data (~430 MB), builds the database and scores every
# company (~20 minutes in total), then starts the site at http://localhost:5173.
# Later runs reuse the data and start in seconds. Pass --refresh to rebuild it.
set -euo pipefail
cd "$(dirname "$0")/.."

refresh=false
[[ "${1:-}" == "--refresh" ]] && refresh=true

need() { command -v "$1" >/dev/null || { echo "Missing $1. $2"; exit 1; }; }
need uv "Install it from https://docs.astral.sh/uv/"
need npm "Install Node.js 22+ from https://nodejs.org/"
if [[ "$(uname)" == "Darwin" ]] && ! { [[ -e /opt/homebrew/opt/libomp ]] || [[ -e /usr/local/opt/libomp ]]; }; then
  echo "LightGBM needs OpenMP on macOS: run 'brew install libomp' first."
  exit 1
fi

uv sync --extra model

if $refresh || [[ ! -f site/public/data/summary.json ]]; then
  if [[ -z "${INVESTUP_USER_AGENT:-}" ]]; then
    echo 'Set INVESTUP_USER_AGENT="Your Name you@example.com" (the SEC requires a contact).'
    exit 1
  fi
  uv run investup download
  uv run investup load
  uv run investup export
fi

cd site
npm install --no-audit --no-fund
npm run dev -- --open
