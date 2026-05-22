# Source Google Sheet — Column Spec

The map widget is driven by a single Google Sheet. `scripts/sync_actions.py` reads
this Sheet daily on Civis, validates rows, and writes `data/states.json`.

## Required setup

1. **Create a new Sheet** named *Common Cause Grassroots Action Map (source-of-truth)*.
2. **Add a tab** named `Actions` (this is the default the script reads — override with `GOOGLE_SHEET_TAB` in `.env` if you use a different name).
3. **Share** the Sheet with the service account email
   (`com-dbt@proj-tmc-mem-com.iam.gserviceaccount.com`) as **Viewer**.
4. **Copy** the Sheet ID from the URL — the long string between `/d/` and `/edit` — into
   `.env` as `GOOGLE_SHEET_ID`.

## Column structure (header row 1)

| Column        | Required | Notes                                                                                     |
|---------------|----------|-------------------------------------------------------------------------------------------|
| `state`       | yes      | Full state name (e.g. `Pennsylvania`). Use `DEFAULT` for the fallback row that covers every state without its own row, plus DC and "Other". |
| `url`         | yes      | Action URL. Must be a valid absolute URL. The script appends `?source=grassroots_map` on render so we can track clicks. |
| `headline`    | yes      | Short headline shown bold at the top of the modal.                                        |
| `description` | yes      | Body copy shown in the modal. Newlines render as paragraphs. Lines starting with `- ` render as bullets. Markdown links `[text](url)` render as plain text (no hyperlinks in the body — the modal only links via the CTA button). |
| `enabled`     | no       | Optional `TRUE`/`FALSE`. Falsy values (`FALSE`/`0`/`no`/`off`/`disabled`) skip that row. Empty/missing → enabled. Use this to temporarily hide a state without deleting its row. |

Header matching is case-insensitive. Whitespace around values is stripped.

## Behavior

- A `DEFAULT` row is required — it powers DC, "Other", and every state without its own row.
- A state row with content **identical to the default** is dropped from `states.json` (the
  embed falls back to default automatically). Organizers can leave such rows in the Sheet
  as drafts; they just don't ship until they diverge from default.
- Rows for `District of Columbia` or `Other` are skipped — those states are hardcoded to
  default in the embed.
- Unknown state names are logged as warnings and skipped.
- Rows missing any of `url` / `headline` / `description` are logged as warnings and skipped.

## Example rows

| state         | url                                                       | headline                                   | description                                                                 | enabled |
|---------------|-----------------------------------------------------------|--------------------------------------------|-----------------------------------------------------------------------------|---------|
| DEFAULT       | https://www.mobilize.us/commoncause/event/758610/         | Phone Bank with Common Cause!              | Join Common Cause for an important phone bank...                            | TRUE    |
| Pennsylvania  | https://docs.google.com/forms/d/e/.../viewform            | Watchdogs for Democracy: County Election Monitoring | Please fill out this form if you are interested in helping...        | TRUE    |
| North Carolina| https://www.mobilize.us/commoncause/event/947580/         | North Carolina Member Call                 | Common Cause NC is hosting a virtual call on May 14, 2026 at 6:00 p.m...     | TRUE    |

## Editorial guidance

- **Keep `description` under ~400 words.** The modal scrolls but readers don't.
- **Use blank lines for paragraphs**, single `\n` inside a paragraph wraps without breaking.
- **Don't put links in `description`.** Use the row's `url` (it powers the "GET STARTED" CTA).
- **Editing the default row affects every state** that isn't individually customized — coordinate
  with the campaigns team before changing it.
