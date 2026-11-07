"""Post docs/summary.md to Discord once per new finished gameweek (optional).

Set a repository secret DISCORD_WEBHOOK to turn this on.
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hook = os.environ.get("DISCORD_WEBHOOK")
if not hook:
    print("No DISCORD_WEBHOOK set; skipping."); sys.exit(0)
res = json.load(open(os.path.join(ROOT, "docs", "results.json")))
latest = max(res["finished_gws"] or [0])
state_p = os.path.join(ROOT, "data", "last_posted.json")
last = json.load(open(state_p))["gw"] if os.path.exists(state_p) else 0
if latest <= last:
    print(f"GW{latest} already posted."); sys.exit(0)
text = open(os.path.join(ROOT, "docs", "summary.md")).read()
page = os.environ.get("PAGE_URL")
if page:
    text += f"\nFull tracker: {page}"
req = urllib.request.Request(hook, data=json.dumps({"content": text[:1990]}).encode(),
                             headers={"Content-Type": "application/json", "User-Agent": "fpl-draft-tracker"})
urllib.request.urlopen(req, timeout=30)
json.dump({"gw": latest}, open(state_p, "w"))
print(f"Posted GW{latest} summary.")
