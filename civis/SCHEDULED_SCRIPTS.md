# Scheduled Scripts — Dynamic Action Map

*Last verified: 2026-05-22*

## Workflows

### Daily Sheet → states.json sync
- **Civis name:** dynamic-action-map daily sync (placeholder — set on Civis Platform)
- **Schedule:** Daily at 06:00 ET (suggested; before commoncause.org morning traffic)
- **Steps:** sync_actions.sh

## Scripts

### sync_actions.sh
- **Type:** Scheduled (via Daily Sheet → states.json sync, step 1)
- **Civis job name:** dynamic-action-map sync_actions
- **APIs:** Google Sheets API (60 reads/min/user), GitHub API (5000 requests/hr/authenticated PAT)
- **Description:** Runs `python scripts/sync_actions.py --push`. Reads the source Google Sheet, writes `data/states.json` if anything changed, then commits and force-no-pushes to `main` via a deploy PAT. GitHub Actions auto-deploys the new JSON to GitHub Pages on push; the embed picks up the change on the next page load. No-op on days when the Sheet is unchanged (the script compares default + states maps before writing).

## On-Demand Scripts

None. Manual runs are done from the developer machine via `python scripts/sync_actions.py` (no `--push`) when previewing changes locally.
