"""Entry point: python -m tracker.main [--offline FIXTURES_DIR]"""
import argparse
import datetime as dt
import json
import os
import sys

import yaml

from .api import DraftApi
from .model import build_players, build_teamweek
from .rules import evaluate
from . import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def finished_gameweeks(game, bootstrap):
    ev = bootstrap.get("events")
    data = ev.get("data") if isinstance(ev, dict) else ev
    fin = sorted(e["id"] for e in (data or []) if e.get("finished"))
    if not fin:
        cur = game.get("current_event") or 0
        fin = list(range(1, cur + 1 if game.get("current_event_finished") else cur))
    return fin, game.get("current_event"), bool(game.get("current_event_finished"))


def drafter_name(le, cfg):
    custom = (cfg.get("drafters") or {}).get(le.get("entry_id"))
    if custom:
        return custom
    first = (le.get("player_first_name") or "").strip()
    return first[:1].upper() + first[1:] if first else le.get("entry_name", "?")


def run(offline_dir=None, out_dir=None):
    with open(os.path.join(ROOT, "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    api = DraftApi(os.path.join(ROOT, "data", "raw"), offline=bool(offline_dir), fixtures_dir=offline_dir)
    out_dir = out_dir or os.path.join(ROOT, "docs")
    os.makedirs(out_dir, exist_ok=True)

    game = api.game()
    bootstrap = api.bootstrap()
    league = api.league(cfg["league_id"])
    for key in ("league", "league_entries"):
        if key not in league:
            raise SystemExit(f"League response missing '{key}' — the API format may have changed.")
    if "elements" not in bootstrap:
        raise SystemExit("bootstrap-static missing 'elements' — the API format may have changed.")

    entries = [le for le in league["league_entries"] if le.get("entry_id")]
    names = {le["entry_id"]: drafter_name(le, cfg) for le in entries}
    teams = {le["entry_id"]: le.get("entry_name", "") for le in entries}

    finished, current, current_done = finished_gameweeks(game, bootstrap)
    refresh = set(finished[-2:])
    teamweeks, warnings = {}, []
    for gw in finished:
        live = api.live(gw, refresh=gw in refresh)
        if "elements" not in live:
            raise SystemExit(f"GW{gw} live data missing 'elements' — the API format may have changed.")
        players = build_players(bootstrap, live)
        rows = []
        for eid in names:
            pj = api.picks(eid, gw, refresh=gw in refresh)
            if not pj.get("picks"):
                warnings.append(f"GW{gw}: no picks for {names[eid]}")
                continue
            tw = build_teamweek(gw, eid, names[eid], teams[eid], pj, players)
            if tw.sub_warning:
                warnings.append(f"GW{gw} {names[eid]}: {tw.sub_warning}")
            rows.append(tw)
        teamweeks[gw] = rows

    hits = evaluate(teamweeks, cfg)

    tx_counts = {}
    try:
        tx = api.transactions(cfg["league_id"])
        for t in tx.get("transactions", []):
            if t.get("result") in ("a", "accepted"):
                tx_counts[t.get("entry")] = tx_counts.get(t.get("entry"), 0) + 1
    except Exception as e:  # transactions are a nice-to-have
        warnings.append(f"transactions unavailable: {e}")

    sheet_path = os.path.join(ROOT, "data", "sheet_marks.json")
    sheet = json.load(open(sheet_path)) if os.path.exists(sheet_path) else None

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=10)))
    ctx = report.build_context(cfg, league, names, teams, teamweeks, hits, tx_counts,
                               finished, current, current_done, warnings, sheet, now)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(report.render_html(ctx))
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write(report.render_summary(ctx))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump({"updated": now.isoformat(), "finished_gws": finished, "hits": hits,
                   "warnings": warnings}, f, indent=1)
    print(report.render_summary(ctx))
    if warnings:
        print("\nWarnings:\n  " + "\n  ".join(warnings))
    return ctx


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", help="read API responses from this folder (tests)")
    ap.add_argument("--out", help="output folder (default docs/)")
    a = ap.parse_args()
    run(a.offline, a.out)
