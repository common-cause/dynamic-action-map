"""
sync_actions.py — pull per-state action content from a Google Sheet, write it to
data/states.json, and (optionally) commit + push to GitHub via the contents API.

Usage:
    python scripts/sync_actions.py              # write states.json; no git push
    python scripts/sync_actions.py --push       # commit + push if states.json changed (Civis mode)
    python scripts/sync_actions.py --dry-run    # show the JSON; write nothing

Env vars (loaded from .env at the project root):
    GOOGLE_SHEETS_CREDENTIALS_PASSWORD          Service account JSON. Read by ccef_connections.
    GOOGLE_SHEET_ID                             The long ID from the Sheet URL.
    GOOGLE_SHEET_TAB                            State-rows tab. Default: "State Campaigns".
    GOOGLE_SHEET_DEFAULT_TAB                    Single-row default tab. Default:
                                                "National Default Campaign".
    DYNAMIC_ACTION_MAP_GITHUB_PAT_PASSWORD      Fine-grained PAT scoped to one repo with
                                                Contents: Read & Write (only for --push).
    GITHUB_REPO                                  owner/repo, e.g. common-cause/dynamic-action-map.

Sheet schema (case-insensitive headers on row 1, see docs/sheet_template.md):
    state        full state name (e.g. "Pennsylvania"). On the default tab, use "DEFAULT".
    url          action URL
    headline     short headline shown in the modal
    description  body text shown in the modal (newlines render as paragraphs; "- " lines render as bullets)
    enabled      optional — "true"/"false"; rows where this is falsy are skipped

State rows on the state-rows tab may be completely blank (only the `state` cell
filled) — those states fall back to the default automatically. Rows on the
state-rows tab that exactly match the default action are also dropped so the
JSON file stays compact.

Rows for DC or "Other" are ignored — those are hardcoded to default in the embed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from ccef_connections import GitHubConnector, SheetsConnector


REPO_ROOT = Path(__file__).resolve().parents[1]
STATES_JSON = REPO_ROOT / "data" / "states.json"
STATES_JSON_REPO_PATH = "data/states.json"  # Path inside the GitHub repo
GITHUB_CREDENTIAL_NAME = "DYNAMIC_ACTION_MAP_GITHUB_PAT"

CANONICAL_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
}

# Sheet rows where the state column matches one of these are treated as the default row.
DEFAULT_KEYS = {"default", "_default_", "default action", "fallback"}


def normalize_row(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        norm_key = str(key).strip().lower()
        norm_val = value.strip() if isinstance(value, str) else value
        out[norm_key] = norm_val
    return out


def is_truthy(value) -> bool:
    if value is None or value == "":
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "off", "disabled")


def normalize_description(s: str) -> str:
    """
    Normalize paragraph separators so Sheet edits don't leak whitespace artifacts.

    Different staff members produce different paragraph-break patterns when
    editing multi-line cells in Google Sheets — some leave a literal space on
    the "blank" line between paragraphs (``"para1\\n \\npara2"``), others
    trail whitespace after sentences. Normalize everything to bare ``\\n\\n``
    so the dedup-against-default check actually fires.
    """
    if not s:
        return s
    lines = [line.strip() for line in s.split("\n")]
    out: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                out.append("")
                blank = True
        else:
            out.append(line)
            blank = False
    return "\n".join(out).strip()


def validate_row(row: dict) -> tuple[str, dict] | None:
    state = row.get("state", "")
    if not state:
        return None
    if not is_truthy(row.get("enabled")):
        return None

    is_default = state.lower() in DEFAULT_KEYS
    if not is_default and state not in CANONICAL_STATES:
        if state in ("District of Columbia", "DC", "Other"):
            print(f"  INFO: '{state}' is always default in the embed — skipping row.", file=sys.stderr)
        else:
            print(f"  WARN: unknown state '{state}' — skipping.", file=sys.stderr)
        return None

    url = row.get("url", "")
    headline = row.get("headline", "")
    description = row.get("description", "")
    # Fully-blank state rows are intentional — the state falls back to default. Silent skip.
    if not url and not headline and not description:
        return None
    # Partial rows are almost certainly an editing mistake. Warn loudly.
    if not url or not headline or not description:
        print(f"  WARN: '{state}' has some but not all of url/headline/description — skipping.", file=sys.stderr)
        return None

    key = "__default__" if is_default else state
    return (key, {
        "url": url,
        "headline": headline,
        "description": normalize_description(description),
    })


def build_states_json(
    state_rows: list[dict],
    default_rows: list[dict],
    previous: dict,
) -> dict:
    # Default resolution order (lowest to highest): previous states.json (so a
    # missing default tab + missing in-tab DEFAULT doesn't wipe out the last
    # known good default), then the dedicated default tab, then any in-tab
    # DEFAULT-keyed row on the state-rows tab.
    default = previous.get("default") or {}
    if default and "description" in default:
        # Normalize previous default so dedup against new sheet rows works.
        default = {**default, "description": normalize_description(default["description"])}

    for raw in default_rows:
        result = validate_row(normalize_row(raw))
        if result and result[0] == "__default__":
            default = result[1]

    states: dict[str, dict] = {}
    for raw in state_rows:
        result = validate_row(normalize_row(raw))
        if not result:
            continue
        key, action = result
        if key == "__default__":
            default = action
        else:
            states[key] = action

    # Strip rows that match default exactly — embed falls back automatically.
    states = {k: v for k, v in states.items() if v != default}

    # Stable key order in JSON output
    states = dict(sorted(states.items()))

    return {
        "_meta": {
            "source": f"Google Sheet sync — {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "schema_version": 1,
        },
        "default": default,
        "states": states,
    }


def serialize(data: dict) -> bytes:
    """Serialize the states data exactly the way it would be written to disk."""
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_json_if_changed(data: dict) -> bool:
    new_bytes = serialize(data)
    # Compare on content only, ignoring the timestamp in _meta.source so identical
    # data doesn't churn the file every day.
    if STATES_JSON.exists():
        old = json.loads(STATES_JSON.read_text(encoding="utf-8"))
        if old.get("default") == data["default"] and old.get("states") == data["states"]:
            return False
    STATES_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATES_JSON.write_bytes(new_bytes)
    return True


def publish_to_github(data: dict, repo: str) -> str | None:
    """
    Publish states.json to the GitHub repo via the contents API.

    Returns the commit SHA if a write happened, or None if the repo already had
    identical bytes. NOTE: serialize() embeds a wall-clock timestamp in
    _meta.source, so these bytes differ on every run — this is NOT idempotent on
    its own. The no-op-day guarantee comes from the caller gating on an actual
    content change (see main); don't call this unconditionally.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with GitHubConnector(credential_name=GITHUB_CREDENTIAL_NAME) as gh:
        return gh.put_file_if_changed(
            repo=repo,
            path=STATES_JSON_REPO_PATH,
            content_bytes=serialize(data),
            message=f"Sync states.json from Google Sheet ({stamp})",
            branch="main",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync per-state action content from Sheet to data/states.json")
    parser.add_argument("--push", action="store_true", help="commit and push if states.json changed (Civis mode)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    state_tab = os.environ.get("GOOGLE_SHEET_TAB", "State Campaigns")
    default_tab = os.environ.get("GOOGLE_SHEET_DEFAULT_TAB", "National Default Campaign")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set in .env", file=sys.stderr)
        return 2

    print(f"Reading sheet {sheet_id} ...")
    # Single connection — fetch both tabs before the context closes.
    with SheetsConnector() as conn:
        spreadsheet = conn.get_spreadsheet(sheet_id)
        default_rows = spreadsheet.worksheet(default_tab).get_all_records()
        state_rows = spreadsheet.worksheet(state_tab).get_all_records()
    print(f"  Default tab '{default_tab}': {len(default_rows)} rows")
    print(f"  State tab '{state_tab}': {len(state_rows)} rows")

    previous: dict = {}
    if STATES_JSON.exists():
        previous = json.loads(STATES_JSON.read_text(encoding="utf-8"))

    data = build_states_json(state_rows, default_rows, previous)

    default_headline = (data["default"].get("headline") or "(none)")[:70]
    print(f"  Default headline: {default_headline}")
    print(f"  Custom state rows: {len(data['states'])}")

    if args.dry_run:
        print("Dry run — not writing.")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    wrote_local = write_json_if_changed(data)
    if wrote_local:
        print(f"Wrote {STATES_JSON.relative_to(REPO_ROOT)}.")
    else:
        print("No changes — local states.json already up to date.")

    if args.push:
        repo = os.environ.get("GITHUB_REPO")
        if not repo:
            print("ERROR: --push requires GITHUB_REPO in env.", file=sys.stderr)
            return 2
        # Only publish when the state content actually changed. serialize() embeds
        # a wall-clock timestamp in _meta.source, so the bytes differ every run;
        # publishing unconditionally would commit (and trigger a Pages deploy)
        # daily even on no-op runs. On Civis the repo is freshly cloned, so
        # wrote_local reflects a genuine change vs what's already on main.
        if not wrote_local:
            print(f"No content change — skipping publish to {repo}.")
        else:
            # GitHubConnector reads DYNAMIC_ACTION_MAP_GITHUB_PAT_PASSWORD via
            # CredentialManager; missing-credential errors surface from there.
            commit_sha = publish_to_github(data, repo)
            if commit_sha:
                print(f"Pushed {commit_sha[:7]} to {repo}.")
            else:
                print(f"No push needed — {repo} already has identical content.")
    else:
        print("Skipped publish (no --push flag).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
