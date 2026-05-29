# Source Google Sheet — Column Spec

The map widget is driven by a Google Sheet with two data tabs. `scripts/sync_actions.py`
reads both daily on Civis, validates rows, and writes `data/states.json`.

## Tabs

| Tab | Purpose | Expected rows |
|---|---|---|
| **National Default Campaign** | One-row tab holding the fallback content used for every state that doesn't have its own override. Also powers DC and "Other". | Header + 1 data row whose `state` cell is `DEFAULT`. |
| **State Campaigns** | One row per state (50 rows). State rows with a URL/headline/description override the default; rows where those cells are blank fall back to default automatically. | Header + up to 50 state rows. |

Tab names are configurable via `GOOGLE_SHEET_TAB` (state-rows tab, default `State Campaigns`)
and `GOOGLE_SHEET_DEFAULT_TAB` (default tab, default `National Default Campaign`).

A third tab `Instructions for Use` is recommended for organizers but is not read by the
script — it's free-form prose explaining the workflow.

## Required setup

1. **Create the Sheet** with the two tabs above.
2. **Share** the Sheet with the service account email
   (`com-dbt@proj-tmc-mem-com.iam.gserviceaccount.com`) as **Viewer**.
3. **Copy** the Sheet ID from the URL — the long string between `/d/` and `/edit` — into
   `.env` as `GOOGLE_SHEET_ID`.

## Column structure (both tabs, header row 1)

| Column        | Required | Notes                                                                                     |
|---------------|----------|-------------------------------------------------------------------------------------------|
| `state`       | yes      | Full state name (e.g. `Pennsylvania`) on the state-rows tab. Use `DEFAULT` on the default tab. |
| `url`         | yes      | Action URL. Must be a valid absolute URL. The embed appends `?source=grassroots_map` on render so clicks are attributable. |
| `headline`    | yes      | Short headline shown bold at the top of the modal.                                        |
| `description` | yes      | Body copy shown in the modal. Newlines render as paragraphs. Lines starting with `- ` render as bullets. Markdown links `[text](url)` render as plain text (no hyperlinks in the body — the modal only links via the CTA button). |
| `enabled`     | no       | Optional `TRUE`/`FALSE`. Falsy values skip the row. Empty/missing → enabled. Use this to temporarily hide a state without deleting its row. |
| `last updated` | no      | Free-form. Ignored by the script; useful as organizer-facing context.                     |
| `updated by`  | no       | Free-form. Ignored by the script.                                                         |

Header matching is case-insensitive. Whitespace around values is stripped, and
description whitespace is normalized — runs of blank/whitespace-only lines collapse to a
single blank line, so paragraph breaks render consistently no matter how each editor
types them.

## Behavior

- The **default tab must have exactly one usable row** (the `DEFAULT` row). If it's
  missing entirely the script falls back to the previous default in `data/states.json`
  rather than fail-hard, but that's a fragile state — keep the default tab populated.
- **Blank state rows fall back to default** automatically (silent skip in the script;
  the embed then uses the default for that state).
- **State rows whose content exactly matches the default** are also dropped, even if all
  three fields are filled. This keeps `states.json` compact for the embed.
- Rows for `District of Columbia` or `Other` on the state-rows tab are skipped — those
  states are hardcoded to default in the embed.
- Unknown state names are logged as warnings and skipped.
- **Partial rows** (some but not all of url/headline/description filled) are logged as
  warnings and skipped — almost always an editing mistake.

## Example

**National Default Campaign tab:**

| state   | url                                                | headline                       | description                              |
|---------|----------------------------------------------------|--------------------------------|------------------------------------------|
| DEFAULT | https://www.mobilize.us/commoncause/event/758610/  | Phone Bank with Common Cause!  | Join Common Cause for an important...    |

**State Campaigns tab (excerpt):**

| state         | url                                                | headline                       | description                              |
|---------------|----------------------------------------------------|--------------------------------|------------------------------------------|
| Alabama       |                                                    |                                |                                          |
| Pennsylvania  | https://docs.google.com/forms/d/e/.../viewform     | Watchdogs for Democracy        | Please fill out this form if you are...  |
| Texas         | https://www.mobilize.us/commoncause/event/...      | Texas Action Team              | ...                                      |

Alabama falls back to default; Pennsylvania and Texas override.

## Editorial guidance

- **Keep `description` under ~400 words.** The modal scrolls but readers don't.
- **Use blank lines for paragraphs**, single `\n` inside a paragraph wraps without breaking. The script normalizes whitespace, so trailing spaces or "blank lines with a space on them" are fine — they all render the same.
- **Don't put links in `description`.** Use the row's `url` (it powers the "GET STARTED" CTA).
- **Editing the DEFAULT row affects every state** that doesn't have its own override — coordinate with the campaigns team before changing it.
