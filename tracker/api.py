"""Thin client for the (unofficial) FPL Draft API, with an on-disk cache.

Finished gameweeks are cached in data/raw/ so the season history survives even
if old endpoints change; the two most recent finished gameweeks are always
re-fetched so late bonus/score corrections are picked up.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://draft.premierleague.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fpl-draft-tracker/1.0)",
    "Accept": "application/json",
}


class ApiError(RuntimeError):
    pass


class DraftApi:
    def __init__(self, raw_dir, offline=False, fixtures_dir=None):
        self.raw_dir = raw_dir
        self.offline = offline          # tests: read only from fixtures_dir
        self.fixtures_dir = fixtures_dir
        os.makedirs(raw_dir, exist_ok=True)

    # --- low level -------------------------------------------------------
    def _cache_path(self, path):
        return os.path.join(self.raw_dir, path.strip("/").replace("/", "__") + ".json")

    def _get(self, path, cache=False, refresh=False):
        cp = self._cache_path(path)
        if self.offline:
            fp = os.path.join(self.fixtures_dir, path.strip("/").replace("/", "__") + ".json")
            if not os.path.exists(fp):
                raise ApiError(f"offline fixture missing: {fp}")
            with open(fp) as f:
                return json.load(f)
        if cache and not refresh and os.path.exists(cp):
            with open(cp) as f:
                return json.load(f)
        last = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(BASE + path, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if cache:
                    with open(cp, "w") as f:
                        json.dump(data, f, separators=(",", ":"))
                return data
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
                last = e
                time.sleep(2 * (attempt + 1))
        raise ApiError(f"GET {path} failed: {last}")

    # --- endpoints ---------------------------------------------------------
    def game(self):
        return self._get("/game")

    def bootstrap(self):
        return self._get("/bootstrap-static")

    def league(self, league_id):
        return self._get(f"/league/{league_id}/details")

    def transactions(self, league_id):
        return self._get(f"/draft/league/{league_id}/transactions")

    def picks(self, entry_id, gw, refresh=False):
        return self._get(f"/entry/{entry_id}/event/{gw}", cache=True, refresh=refresh)

    def live(self, gw, refresh=False):
        return self._get(f"/event/{gw}/live", cache=True, refresh=refresh)
