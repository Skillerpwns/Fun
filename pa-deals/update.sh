#!/usr/bin/env bash
# Scan every store, then open the deals site.
cd "$(dirname "$0")"
source .venv/bin/activate
python -m padeals scrape
python -m padeals serve
