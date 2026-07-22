# Dynamic Action Map

Sheet-driven version of the commoncause.org state grassroots map. Replaces a 680-line
inline WordPress block (preserved in the meta-project's `docs/grassrootsmap.html`,
not in this repo) with a thin embed + daily Civis sync from a Google Sheet.

## Current Status (2026-07-07)

Live on Civis: the GitHub-backed sync job is created and scheduled daily at 06:00 ET
with a failure-trigger email to rkerth. The write path from Civis is confirmed (see
below). What's left: verify the web-team embed swap on the live commoncause.org page
(Rob believes it's done, but it's unconfirmed and the host page URL was never recorded
— see `.claude/handoff.md`). No organic content-change push has landed on `main` since
go-live (origin checked 2026-07-07) — the Sheet hasn't changed, so the first live
end-to-end `Pushed <sha>` is still pending, which is expected.

**Done:**
- Repo published at `github.com/common-cause/dynamic-action-map`, branch `main`,
  GitHub Pages enabled. Embed loadable at
  `https://common-cause.github.io/dynamic-action-map/src/embed.js`
- Sync script publishes via `ccef_connections.GitHubConnector` (no `subprocess git`
  or checkout on the Civis worker). Per-repo credential: `DYNAMIC_ACTION_MAP_GITHUB_PAT`
- Source Sheet built (ID in `.env`) with the two-tab pattern:
  - `National Default Campaign` — single DEFAULT row
  - `State Campaigns` — 50 state rows, blank rows fall back to default automatically
- Script reads both tabs, normalizes description whitespace, dedupes default-equivalent
  rows. 17 custom state rows + default.
- `DYNAMIC_ACTION_MAP_GITHUB_PAT` provisioned as a Civis credential and verified. (The
  initial paste was truncated → "bad credentials"; re-pasted, confirmed via a len/prefix
  probe.) The PAT value is proven able to write — a local `--push` pushed `3c2fe73`.
- Civis GitHub-backed script job created — image `civisanalytics/datascience-python:latest`,
  body `bash app/civis/sync_actions.sh`, scheduled daily 06:00 ET, failure email to rkerth.
- Idempotency fix (`de3dd93`): publish is gated on an actual content change, not the
  `_meta.source` timestamp — no-op days no longer churn a commit + Pages deploy.
- `.gitattributes` pins `*.sh` to LF (`5171d66`) so the Civis entrypoint can't pick up
  CRLF on this Windows/OneDrive repo (CRLF = bad-interpreter error in the Linux container).

**Pending:**
1. Web team swap of the WP block to the two-line embed snippet.

**Write path confirmed from Civis (2026-06-19).** A temp `civis/check_pat.py` probe
run from the Civis job showed the credential holds the proven token (sha256 `7480ebdc…`),
authenticates from Civis's network (`rate_limit` core = 5000, not the anonymous 60), and
has repo write access (`push=True`). The earlier "bad credentials" was just a wrong/garbled
token in the Civis credential; re-pasting the `.env` value fixed it. No org IP allow list
or egress issue. Probe removed after confirmation. The next organic Sheet edit will produce
the first live `Pushed <sha>` end-to-end.

The Massachusetts typos noted in earlier status are already fixed in the Sheet
(Geoff Foster, 3/22/2026); `states.json` matches — nothing to sync.

## Project Type: cc-embed (with Python sync layer)

cc-embed default has no venv, but this project adds one because of the Python sync
script. Venv lives at `C:/venvs/dynamic-action-map/` with a junction at `.venv` —
the standard Windows/OneDrive pattern.

## Key Files

- `src/embed.js` / `src/embed.css` — the widget. Finds `#cc-grassroots-map-embed`,
  fetches `data/states.json`, renders Google GeoChart + a modal with the state's
  action. Has a hardcoded fallback action if `states.json` fails to load.
- `data/states.json` — per-state action content. Owned by `sync_actions.py` in prod;
  safe to edit by hand for one-off fixes.
- `scripts/sync_actions.py` — Sheet → states.json pipeline. Validates rows, dedupes
  default-equivalent state rows, writes atomically, optionally commits + pushes.
- `docs/sheet_template.md` — Google Sheet column spec for organizers.
- `civis/SCHEDULED_SCRIPTS.md` — Civis scheduling docs.
- `docs/grassrootsmap.html` — the original inline WP block, kept as reference until
  the new embed is verified live on commoncause.org. (This lives in the meta-project's
  docs/ — not duplicated here.)

## Architecture Notes

**Mount id is `cc-grassroots-map-embed`**, not the cc-embed-template default of
`cc-tool`. All CSS uses the existing `ccgm-*` class names — preserved from the
original block to keep the styles legible and avoid churn.

**Falls back to default for any state not in `states.json`.** The Sheet only needs
rows for states whose action diverges from the org-wide default. The sync drops
default-equivalent rows automatically.

**`?source=grassroots_map` is appended to every CTA URL** so clicks are attributable
in downstream analytics.

**DC and "Other" are always default** — hardcoded in `embed.js` to use the DEFAULT
action regardless of what the Sheet says.

## Local Development

```bash
# Preview the embed in a browser
python -m http.server 8080
# Open http://localhost:8080

# Preview the sync without writing
.venv\Scripts\python scripts/sync_actions.py --dry-run

# Run the sync, write states.json, no push (safe local default)
.venv\Scripts\python scripts/sync_actions.py
```

## Civis Schedule

`sync_actions.py --push` runs daily at 06:00 ET via a GitHub-backed Civis job
(`bash app/civis/sync_actions.sh`). See
`civis/SCHEDULED_SCRIPTS.md` for details. The script is idempotent — a no-op day
produces no commit. Auto-deploy via GitHub Actions on every push to `main`.

## WordPress Embed Snippet

```html
<div id="cc-grassroots-map-embed"></div>
<script src="https://common-cause.github.io/dynamic-action-map/src/embed.js"></script>
```

Replaces the existing 680-line inline block on the target page. Web team handles the
swap when this project ships.

## Gotchas

- **CORS on local dev:** opening `index.html` via `file://` will break the
  `states.json` fetch. Always serve via `python -m http.server` locally.
- **The hardcoded fallback default in `embed.js`** must be kept in sync with the
  `DEFAULT` row in the Sheet — otherwise a fetch failure surfaces stale copy. Low
  cost to keep aligned; worth noting.
- **GitHub Pages enablement:** needs `enablement: true` in the Actions
  `configure-pages` step (already set in `deploy.yml`) the first time, or the deploy
  fails until Pages is enabled manually in repo Settings.
- **ccef-connections install paths differ by environment:** `requirements.txt`
  points to a local `file:///` URL (this machine's OneDrive checkout) for local
  runs; the Civis job instead installs from the pinned Git tag in
  `civis/sync_actions.sh` (`ccef-connections[sheets] @ git+…@v0.2.0`). Bump the
  tag there deliberately when upgrading.
- **Sheet column headers are case-insensitive** but column names matter (`headline`,
  not `Heading`). Whitespace around values is stripped.

## PII / Data Handling

Row-level PII (names, emails, phones, street addresses, gift amounts) **never gets
committed to git** — repos here are org-visible via shared corpora and export pipelines.
Any directory that will receive raw dumps or query results gets gitignored BEFORE the
first file lands (allowlist known-clean file types; never enumerate known-bad files).
Committed derivatives must be masked or aggregated; fabricate example rows in docs.
Row-level people-data lives in access-controlled systems (BigQuery, ROI, Action Network,
shared Sheets) — point at it, don't copy it. Full policy: knowledge library entry
`pii-handling-policy` (`kl_get`).
