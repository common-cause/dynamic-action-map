#!/usr/bin/env bash
# Civis entrypoint for the daily Sheet -> states.json -> GitHub Pages sync.
# GitHub-backed job: Civis clones this repo into app/, so set the job body to:
#     bash app/civis/sync_actions.sh
# Edit this file (not the Civis UI) to change setup/run steps. See
# civis/SCHEDULED_SCRIPTS.md for the schedule, credentials, and env vars.
#
# Not for local use — run `python scripts/sync_actions.py` (no --push) locally.
set -euo pipefail

# Image (civisanalytics/datascience-python) ships python-dotenv; the [sheets]
# extra brings gspread + google-auth. Pinned to a ccef-connections release
# tag — bump deliberately when upgrading.
pip install "ccef-connections[sheets] @ git+https://github.com/common-cause/ccef_connections.git@v0.2.0"

python app/scripts/sync_actions.py --push
