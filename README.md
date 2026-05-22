# Dynamic Action Map

Sheet-driven version of the commoncause.org state grassroots action map. An organizer-editable Google Sheet drives per-state action content; a daily Civis script syncs the Sheet to `data/states.json` and pushes to GitHub Pages, where the embed picks it up automatically.

Replaces the static `docs/grassrootsmap.html` block previously pasted into the WordPress page.

## How it works

```
Google Sheet (organizers edit)
        │  Civis script (daily, 06:00 ET)
        ▼
data/states.json  ──git push──►  GitHub Pages
                                       │
                                       ▼  (fetched at page load)
                                 commoncause.org embed
```

- **The widget** (`src/embed.js`, `src/embed.css`) — pure HTML/CSS/JS. Loads `data/states.json` from the same GitHub Pages origin and renders a clickable US map plus a state dropdown. Built on Google Charts GeoChart, identical UX to the old inline block. Falls back to a hardcoded default if `states.json` 404s, so the page never breaks.
- **The data** (`data/states.json`) — single source of truth for what each state shows. Owned by the sync script in production; safe to edit by hand for one-off fixes too.
- **The sync** (`scripts/sync_actions.py`) — reads the source Sheet, validates rows, builds `states.json`, and (with `--push`) commits + pushes. Idempotent — only commits when content changes.

## WordPress embed (two lines)

```html
<div id="cc-grassroots-map-embed"></div>
<script src="https://common-cause.github.io/dynamic-action-map/src/embed.js"></script>
```

Replaces the entire 680-line inline block that's there today.

## Setup

1. **Create the Google Sheet** following `docs/sheet_template.md`. Share with the SA email.
2. **Configure `.env`** — fill in `GOOGLE_SHEET_ID`. The sheets credential is already seeded. For Civis runs, also set `GITHUB_TOKEN` and `GITHUB_REPO`.
3. **First sync (local):**
   ```bash
   .venv\Scripts\python scripts/sync_actions.py --dry-run    # preview
   .venv\Scripts\python scripts/sync_actions.py              # write states.json
   ```
4. **Push to GitHub** — create the repo at `github.com/common-cause/dynamic-action-map`, push `main`, enable Pages in repo Settings → Pages → Source: GitHub Actions.
5. **Schedule on Civis** — wrap the sync in `civis/sync_actions.sh` (TODO: add this shell wrapper once the Civis Platform project is set up). Pass `--push` so changes ship.

## Local Development

The embed needs an HTTP server to fetch `states.json` without CORS errors:

```bash
python -m http.server 8080
# Open http://localhost:8080
```

## Project Structure

```
dynamic-action-map/
├── index.html                  # Local dev preview wrapper (not deployed)
├── src/
│   ├── embed.js                # Widget — finds #cc-grassroots-map-embed, fetches states.json, renders map
│   └── embed.css               # Styles, all scoped under #cc-grassroots-map-embed or .ccgm-*
├── data/
│   └── states.json             # Per-state action content. Auto-written by sync_actions.py.
├── scripts/
│   └── sync_actions.py         # Pull from Sheet, write states.json, optionally git push
├── civis/
│   └── SCHEDULED_SCRIPTS.md    # Civis scheduling docs (rolls up into meta-project cloud_schedule.md)
├── docs/
│   └── sheet_template.md       # Google Sheet column spec for organizers
├── requirements.txt            # gspread, google-auth, python-dotenv, ccef-connections
└── .github/workflows/deploy.yml  # Auto-deploy to GitHub Pages on push to main
```

## Reusability

This project is a working pattern for *any* Sheet-driven embed where content lives in a
Sheet and the deploy target is GitHub Pages. The split between `src/embed.js` (presentation)
and `scripts/sync_actions.py` (data pipeline) is intentionally clean — if you build a
second similar tool, lift `sync_actions.py` and adapt the validation step. The
`ccef_connections.SheetsConnector` import is the only org-specific dependency.
