"""TEMP diagnostic — characterize DYNAMIC_ACTION_MAP_GITHUB_PAT from wherever it runs.

Set the Civis job body to `python app/civis/check_pat.py`, run, read the log.
Stdlib only (no pip install). On Civis the credential is a real env var; locally
it loads .env. DELETE this file once the credential is confirmed.
"""
import os, json, hashlib
import urllib.request as u
import urllib.error as e

try:
    from dotenv import load_dotenv
    load_dotenv()  # harmless no-op on Civis (no .env present)
except Exception:
    pass

p = os.environ.get("DYNAMIC_ACTION_MAP_GITHUB_PAT_PASSWORD", "").strip()
sha8 = hashlib.sha256(p.encode()).hexdigest()[:8] if p else "EMPTY"
print(f"token sha256[:8]={sha8} len={len(p)}")


def probe(url):
    req = u.Request(url, headers={
        "Authorization": "Bearer " + p,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        r = u.urlopen(req)
        return r.status, json.load(r)
    except e.HTTPError as ex:
        return ex.code, ex.read().decode()[:300]


s, b = probe("https://api.github.com/rate_limit")
limit = b.get("resources", {}).get("core", {}).get("limit") if isinstance(b, dict) else b
print(f"rate_limit -> HTTP {s}  core_limit={limit}   (5000=authenticated, 60=anonymous)")

s, b = probe("https://api.github.com/repos/common-cause/dynamic-action-map")
if isinstance(b, dict):
    print(f"repos      -> HTTP {s}  has_permissions={'permissions' in b}  push={b.get('permissions', {}).get('push')}")
else:
    print(f"repos      -> HTTP {s}  body={b}")
