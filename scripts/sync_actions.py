"""
sync_actions.py — pull per-state action content from a Google Sheet, write it to
data/states.json, and (optionally) commit + push to GitHub Pages.

Usage:
    python scripts/sync_actions.py              # write states.json; no git push
    python scripts/sync_actions.py --push       # commit + push if states.json changed (Civis mode)
    python scripts/sync_actions.py --dry-run    # show the JSON; write nothing

Env vars (loaded from .env at the project root):
    GOOGLE_SHEETS_CREDENTIALS_PASSWORD  Service account JSON. Read by ccef_connections.
    GOOGLE_SHEET_ID                     The long ID from the Sheet URL.
    GOOGLE_SHEET_TAB                    Worksheet tab name. Default: "Actions".
    GITHUB_TOKEN                        PAT with contents:write on the repo (only for --push).
    GITHUB_REPO                         owner/repo, e.g. common-cause/dynamic-action-map (only for --push).

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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from ccef_connections import SheetsConnector


REPO_ROOT = Path(__file__).resolve().parents[1]
STATES_JSON = REPO_ROOT / "data" / "states.json"

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


def write_json_if_changed(data: dict) -> bool:
    new_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # Compare on content only, ignoring the timestamp in _meta.source so identical
    # data doesn't churn the file every day.
    if STATES_JSON.exists():
        old = json.loads(STATES_JSON.read_text(encoding="utf-8"))
        if old.get("default") == data["default"] and old.get("states") == data["states"]:
            return False
    STATES_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATES_JSON.write_text(new_text, encoding="utf-8")
    return True


def git_commit_and_push(token: str, repo: str) -> None:
    env = os.environ.copy()
    run = lambda *args: subprocess.run(list(args), check=True, cwd=REPO_ROOT, env=env)
    run("git", "config", "user.email", "actions@common-cause.org")
    run("git", "config", "user.name", "dynamic-action-map sync")
    run("git", "add", "data/states.json")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run("git", "commit", "-m", f"Sync states.json from Google Sheet ({stamp})")
    push_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    run("git", "push", push_url, "HEAD:main")


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

    if write_json_if_changed(data):
        print(f"Wrote {STATES_JSON.relative_to(REPO_ROOT)}.")
    else:
        print("No changes — states.json already up to date.")
        return 0

    if args.push:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPO")
        if not token or not repo:
            print("ERROR: --push requires GITHUB_TOKEN and GITHUB_REPO in env.", file=sys.stderr)
            return 2
        git_commit_and_push(token, repo)
        print(f"Pushed to {repo}.")
    else:
        print("Skipped git push (no --push flag).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
