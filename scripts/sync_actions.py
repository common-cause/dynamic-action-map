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
    GOOGLE_SHEET_TAB                            Worksheet tab name. Default: "Actions".
    DYNAMIC_ACTION_MAP_GITHUB_PAT_PASSWORD      Fine-grained PAT scoped to one repo with
                                                Contents: Read & Write (only for --push).
    GITHUB_REPO                                  owner/repo, e.g. common-cause/dynamic-action-map.

Sheet schema (case-insensitive header row, see docs/sheet_template.md):
    state        full state name (e.g. "Pennsylvania"), or "DEFAULT" for the fallback row
    url          action URL
    headline     short headline shown in the modal
    description  body text shown in the modal (newlines render as paragraphs; "- " lines render as bullets)
    enabled      optional — "true"/"false"; rows where this is falsy are skipped

Rows whose action matches the default exactly are dropped from `states` (the widget
falls back to default for any state not present). Rows for DC or "Other" are ignored —
those are hardcoded to default in the embed.
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


def fetch_sheet_rows(sheet_id: str, tab_name: str) -> list[dict]:
    with SheetsConnector() as conn:
        spreadsheet = conn.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(tab_name)
        return worksheet.get_all_records()


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
    if not url or not headline or not description:
        print(f"  WARN: '{state}' missing url/headline/description — skipping.", file=sys.stderr)
        return None

    key = "__default__" if is_default else state
    return (key, {"url": url, "headline": headline, "description": description})


def build_states_json(rows: list[dict], previous: dict) -> dict:
    default = previous.get("default") or {}
    states: dict[str, dict] = {}

    for raw in rows:
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

    Returns the commit SHA if a write happened, or None if the repo already
    had identical content (idempotent — no-op days produce no commits).
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
    tab_name = os.environ.get("GOOGLE_SHEET_TAB", "Actions")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set in .env", file=sys.stderr)
        return 2

    print(f"Reading sheet {sheet_id} / tab '{tab_name}' ...")
    rows = fetch_sheet_rows(sheet_id, tab_name)
    print(f"  {len(rows)} rows in sheet.")

    previous: dict = {}
    if STATES_JSON.exists():
        previous = json.loads(STATES_JSON.read_text(encoding="utf-8"))

    data = build_states_json(rows, previous)

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
