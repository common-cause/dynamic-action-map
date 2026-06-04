# Scheduled Scripts — Dynamic Action Map

*Last verified: 2026-06-04*

## Workflows

### Daily Sheet → states.json sync
- **Civis name:** dynamic-action-map daily sync (placeholder — set on Civis Platform)
- **Schedule:** Daily at 06:00 ET (suggested; before commoncause.org morning traffic)
- **Steps:** sync_actions.sh

## Scripts

### sync_actions.sh
- **Type:** Scheduled (via Daily Sheet → states.json sync, step 1)
- **Civis job name:** dynamic-action-map sync_actions
- **Source script:** `civis/sync_actions.sh` (version-controlled job body)
- **APIs:** Google Sheets API (60 reads/min/user), GitHub API (5000 requests/hr/authenticated PAT)
- **Description:** Runs `python scripts/sync_actions.py --push`. Reads the source Google Sheet, writes `data/states.json` if anything changed, then commits and force-no-pushes to `main` via a deploy PAT. GitHub Actions auto-deploys the new JSON to GitHub Pages on push; the embed picks up the change on the next page load. No-op on days when the Sheet is unchanged (the script compares default + states maps before writing).

#### Civis configuration

| Field | Value |
|---|---|
| Source repo | `common-cause/dynamic-action-map` |
| Branch | `main` |
| Docker image | `civisanalytics/datascience-python:latest` |
| Command | `bash app/civis/sync_actions.sh` |

The job is **GitHub-backed**: Civis clones the repo into `app/` and runs the
stub command above. Setup/run steps live in the version-controlled
`civis/sync_actions.sh` — edit and push to change them; never edit the script
body in the Civis UI. Credentials/env the job must provide (see the
`sync_actions.py` docstring): `GOOGLE_SHEETS_CREDENTIALS` (service-account
JSON in the password field), `DYNAMIC_ACTION_MAP_GITHUB_PAT` (fine-grained
deploy PAT in the password field), plus `GOOGLE_SHEET_ID` and `GITHUB_REPO`
as job parameters — carry these over from the pre-conversion job when
switching to the stub body.

## On-Demand Scripts

None. Manual runs are done from the developer machine via `python scripts/sync_actions.py` (no `--push`) when previewing changes locally.
