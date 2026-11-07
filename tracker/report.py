"""Dashboard (docs/index.html) and group-chat summary (docs/summary.md)."""
from html import escape as e


def build_context(cfg, league, names, teams, teamweeks, hits, tx_counts,
                  finished, current, current_done, warnings, now):
    drafters = list(names.values())
    eid_by_name = {v: k for k, v in names.items()}
    gws = sorted(teamweeks)
    pts = {d: {} for d in drafters}
    bench = {d: 0 for d in drafters}
    for gw in gws:
        for tw in teamweeks[gw]:
            pts[tw.drafter][gw] = tw.points
            bench[tw.drafter] += sum(p.points for p in tw.final_bench)
    total = {d: sum(pts[d].values()) for d in drafters}
    order = sorted(drafters, key=lambda d: (-total[d], d))

    rules = cfg["prizes"] + cfg["forfeits"]
    grid = {r["id"]: {d: [] for d in drafters} for r in rules}
    for h in hits:
        grid[h["rule"]][h["drafter"]].append(h["gw"])
    n_prize = {d: sum(1 for h in hits if h["kind"] == "prize" and h["drafter"] == d) for d in drafters}
    n_forf = {d: sum(1 for h in hits if h["kind"] == "forfeit" and h["drafter"] == d) for d in drafters}
    money_rules = {r["id"] for r in cfg["prizes"] if r.get("money")}
    money = {d: 0.0 for d in drafters}
    for h in hits:
        if h["rule"] in money_rules:
            money[h["drafter"]] += cfg["first_to_prize_money"] * h["share"]

    latest = gws[-1] if gws else None
    latest_rows = sorted(teamweeks.get(latest, []), key=lambda t: -t.points) if latest else []

    hi = max(n_prize.values()) if n_prize else 0
    lo = min(n_prize.values()) if n_prize else 0
    return dict(cfg=cfg, league_name=league["league"].get("name", "FPL Draft"),
                drafters=drafters, order=order, teams={names[k]: v for k, v in teams.items()},
                tx={d: tx_counts.get(eid_by_name[d], 0) for d in drafters},
                gws=gws, pts=pts, total=total, bench=bench, grid=grid, hits=hits,
                n_prize=n_prize, n_forf=n_forf, money=money, latest=latest, latest_rows=latest_rows,
                current=current, current_done=current_done, warnings=warnings, now=now,
                most=[d for d in drafters if n_prize[d] == hi], least=[d for d in drafters if n_prize[d] == lo],
                rule_name={r["id"]: r["name"] for r in rules},
                rule_text={r["id"]: r.get("reward") or r.get("forfeit") for r in rules})


# ---------------------------------------------------------------- summary --
def render_summary(c):
    if not c["latest"]:
        return "No finished gameweeks yet."
    gw = c["latest"]
    rows = c["latest_rows"]
    lines = [f"⚽ {c['league_name']} — GW{gw} wrap", ""]
    lines.append(f"🔝 Top score: {rows[0].drafter} {rows[0].points}")
    lines.append(f"🪣 Wooden spoon: {rows[-1].drafter} {rows[-1].points}")
    lines.append("")
    lines.append("📊 Table")
    for i, d in enumerate(c["order"], 1):
        lines.append(f"{i}. {d} — {c['total'][d]} ({c['pts'][d].get(gw, 0)} this GW)")
    week = [h for h in c["hits"] if h["gw"] == gw]
    pr = [h for h in week if h["kind"] == "prize"]
    fo = [h for h in week if h["kind"] == "forfeit"]
    lines.append("")
    lines.append("🏆 Minor prizes")
    lines += [f"• {h['drafter']}: {c['rule_name'][h['rule']]} — {h['detail']} → {c['rule_text'][h['rule']]}"
              for h in pr] or ["• None this week"]
    lines.append("")
    lines.append("🍺 Minor forfeits")
    lines += [f"• {h['drafter']}: {c['rule_name'][h['rule']]} — {h['detail']} → {c['rule_text'][h['rule']]}"
              for h in fo] or ["• Clean week, somehow"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- html --
CSS = """
:root{--ink:#1d1630;--muted:#6b6380;--line:#e7e3ef;--bg:#faf9fc;--card:#fff;--accent:#5b2ca0;
--good:#0f7a4a;--goodbg:#e3f5ec;--bad:#b3261e;--badbg:#fbe6e4;}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
color:var(--ink);background:var(--bg)}
header{background:var(--accent);color:#fff;padding:20px 16px}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;opacity:.85;font-size:13px}
main{max-width:1100px;margin:0 auto;padding:16px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 16px}
h2{font-size:17px;margin:0 0 10px}h3{font-size:14px;margin:14px 0 6px;color:var(--muted)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px}td.num,th.num{text-align:right}
td.wrap{white-space:normal;min-width:220px}.reward{color:var(--muted);font-size:12px}
.chip{display:inline-block;padding:1px 6px;border-radius:9px;font-size:12px;margin:1px}
.p{background:var(--goodbg);color:var(--good)}.f{background:var(--badbg);color:var(--bad)}
.hi{background:var(--goodbg);font-weight:600}.lo{background:var(--badbg);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.card{border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card b{display:block;font-size:20px}.card span{color:var(--muted);font-size:12px}
nav{background:#fff;border-bottom:1px solid var(--line);display:flex;gap:4px;padding:0 12px;overflow-x:auto;position:sticky;top:0;z-index:5}
nav a{padding:12px 14px;color:var(--muted);text-decoration:none;font-weight:600;font-size:14px;white-space:nowrap;border-bottom:3px solid transparent}
nav a.on{color:var(--accent);border-bottom-color:var(--accent)}
ul{margin:4px 0;padding-left:18px}li{margin:3px 0}.warn{color:var(--muted);font-size:12px}
"""


def _week_list(c, kind, gw):
    hs = [h for h in c["hits"] if h["gw"] == gw and h["kind"] == kind]
    if not hs:
        return "<p class='reward'>None this week.</p>"
    return "<ul>" + "".join(
        f"<li><b>{e(h['drafter'])}</b> — {e(c['rule_name'][h['rule']])}: {e(h['detail'])}"
        f"<br><span class='reward'>→ {e(c['rule_text'][h['rule']])}</span></li>" for h in hs) + "</ul>"


def _grid(c, rules, cls):
    head = "".join(f"<th>{e(d)}</th>" for d in c["order"])
    body = []
    for r in rules:
        cells = "".join(
            "<td>" + "".join(f"<span class='chip {cls}'>GW{g}</span>" for g in c["grid"][r["id"]][d]) + "</td>"
            for d in c["order"])
        body.append(f"<tr><td class='wrap'>{e(r['name'])}<br><span class='reward'>"
                    f"{e(r.get('reward') or r.get('forfeit'))}</span></td>{cells}</tr>")
    return f"<div class='scroll'><table><tr><th>Rule</th>{head}</tr>{''.join(body)}</table></div>"


PAGES = [("index.html", "Gameweek Summary"), ("prizes.html", "Minor Prizes"),
         ("forfeits.html", "Minor Forfeits")]


def render_html(c):
    cfg, gw = c["cfg"], c["latest"]
    status = (f"Updated through GW{gw}" if gw else "No finished gameweeks yet")
    if c["current"] and not c["current_done"] and c["current"] != gw:
        status += f" · GW{c['current']} in progress"
    def page_head(active):
        tabs = "".join(f"<a href='{f}' class='{'on' if f == active else ''}'>{e(t)}</a>" for f, t in PAGES)
        return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{e(c['league_name'])} tracker</title><style>{CSS}</style></head><body>"
                f"<header><h1>{e(c['league_name'])}</h1><p>{status} · refreshed "
                f"{c['now'].strftime('%a %d %b %Y, %I:%M %p')} Brisbane</p></header>"
                f"<nav>{tabs}</nav><main>")
    foot = ("<p class='reward' style='text-align:center'>Data from the FPL Draft site (unofficial feed). "
            "Rules live in config.yaml.</p></main></body></html>")
    out = []

    if gw:
        rows = c["latest_rows"]
        out.append(f"<section><h2>GW{gw} wrap</h2><div class='cards'>"
                   f"<div class='card'><span>Top score</span><b>{rows[0].points}</b>{e(rows[0].drafter)}</div>"
                   f"<div class='card'><span>Wooden spoon</span><b>{rows[-1].points}</b>{e(rows[-1].drafter)}</div>"
                   f"<div class='card'><span>Most bench points</span>"
                   f"<b>{max(sum(p.points for p in t.final_bench) for t in rows)}</b>"
                   f"{e(max(rows, key=lambda t: sum(p.points for p in t.final_bench)).drafter)}</div></div>"
                   f"<h3>Minor prizes</h3>{_week_list(c, 'prize', gw)}"
                   f"<h3>Minor forfeits</h3>{_week_list(c, 'forfeit', gw)}</section>")

    # standings
    sips_top = cfg.get("awards_night_sips_top", 8)
    trs = []
    for i, d in enumerate(c["order"], 1):
        last5 = [c["pts"][d].get(g) for g in c["gws"][-5:]]
        last5 = [x for x in last5 if x is not None]
        form = round(sum(last5) / len(last5), 1) if last5 else 0
        trs.append(f"<tr><td>{i}</td><td><b>{e(d)}</b><br><span class='reward'>{e(c['teams'][d])}</span></td>"
                   f"<td class='num'>{c['pts'][d].get(gw, '')}</td><td class='num'><b>{c['total'][d]}</b></td>"
                   f"<td class='num'>{form}</td><td class='num'>{c['bench'][d]}</td><td class='num'>{c['tx'][d]}</td>"
                   f"<td class='num'>{c['n_prize'][d]}</td><td class='num'>{c['n_forf'][d]}</td>"
                   f"<td class='num'>{'$%g' % c['money'][d] if c['money'][d] else ''}</td>"
                   f"<td class='num'>{max(sips_top - i + 1, 0)}</td></tr>")
    out.append("<section><h2>Standings</h2><div class='scroll'><table><tr><th>#</th><th>Drafter</th>"
               "<th class='num'>GW</th><th class='num'>Total</th><th class='num'>Form (last 5)</th>"
               "<th class='num'>Bench pts</th><th class='num'>Transactions</th><th class='num'>Prizes</th>"
               "<th class='num'>Forfeits</th><th class='num'>Prize $</th><th class='num'>Sips to give out*</th></tr>"
               + "".join(trs) + "</table></div><p class='reward'>* Awards night, based on current position. "
               "Prizes, forfeits and $ are minor ones only.</p></section>")

    # race + season awards
    races = []
    for r in cfg["prizes"]:
        if not r.get("first_only"):
            continue
        won = [h for h in c["hits"] if h["rule"] == r["id"]]
        txt = (", ".join(f"{h['drafter']} (GW{h['gw']})" for h in won) if won else "Unclaimed")
        races.append(f"<li>{e(r['name'])}: <b>{e(txt)}</b></li>")
    out.append(f"<section><h2>Races &amp; season awards</h2><ul>{''.join(races)}</ul>"
               f"<h3>Most minor achievements (currently)</h3><p><b>{e(', '.join(c['most']))}</b> — "
               f"{e(cfg['season_awards']['most'])}</p>"
               f"<h3>Least minor achievements (currently)</h3><p><b>{e(', '.join(c['least']))}</b> — "
               f"{e(cfg['season_awards']['least'])}</p></section>")


    # GW points matrix
    head = "".join(f"<th class='num'>{g}</th>" for g in c["gws"])
    body = []
    for d in c["order"]:
        tds = []
        for g in c["gws"]:
            col = [c["pts"][x].get(g) for x in c["drafters"] if c["pts"][x].get(g) is not None]
            v = c["pts"][d].get(g)
            cls = "hi" if col and v == max(col) else "lo" if col and v == min(col) else ""
            tds.append(f"<td class='num {cls}'>{'' if v is None else v}</td>")
        body.append(f"<tr><td><b>{e(d)}</b></td>{''.join(tds)}</tr>")
    out.append(f"<section><h2>Points by gameweek</h2><div class='scroll'><table><tr><th>Drafter</th>{head}</tr>"
               f"{''.join(body)}</table></div><p class='reward'>Green = week's high, red = week's low.</p></section>")

    if c["warnings"]:
        out.append("<section><h2>Data notes</h2><ul class='warn'>" +
                   "".join(f"<li>{e(w)}</li>" for w in c["warnings"]) + "</ul></section>")
    pages = {"index.html": page_head("index.html") + "".join(out) + foot}

    # --- Minor prizes page
    by = sorted(c["drafters"], key=lambda d: (-c["n_prize"][d], d))
    rows = "".join(f"<tr><td><b>{e(d)}</b></td><td class='num'>{c['n_prize'][d]}</td>"
                   f"<td class='num'>{'$%g' % c['money'][d] if c['money'][d] else ''}</td></tr>" for d in by)
    recent = [h for h in c["hits"] if h["kind"] == "prize"][::-1][:15]
    rec = "".join(f"<li>GW{h['gw']} · <b>{e(h['drafter'])}</b> — {e(c['rule_name'][h['rule']])}: {e(h['detail'])}</li>"
                  for h in recent) or "<li>None yet.</li>"
    pages["prizes.html"] = (page_head("prizes.html") +
        f"<section><h2>Minor achievements tally</h2><div class='scroll'><table><tr><th>Drafter</th>"
        f"<th class='num'>Achievements</th><th class='num'>Prize $</th></tr>{rows}</table></div>"
        f"<p class='reward'>Most (currently): <b>{e(', '.join(c['most']))}</b> — {e(cfg['season_awards']['most'])}<br>"
        f"Least (currently): <b>{e(', '.join(c['least']))}</b> — {e(cfg['season_awards']['least'])}</p></section>"
        f"<section><h2>Minor prizes tracker</h2>{_grid(c, cfg['prizes'], 'p')}</section>"
        f"<section><h2>Recent prizes</h2><ul>{rec}</ul></section>" + foot)

    # --- Minor forfeits page
    by = sorted(c["drafters"], key=lambda d: (-c["n_forf"][d], d))
    rows = "".join(f"<tr><td><b>{e(d)}</b></td><td class='num'>{c['n_forf'][d]}</td></tr>" for d in by)
    recent = [h for h in c["hits"] if h["kind"] == "forfeit"][::-1][:15]
    rec = "".join(f"<li>GW{h['gw']} · <b>{e(h['drafter'])}</b> — {e(c['rule_name'][h['rule']])}: {e(h['detail'])}"
                  f"<br><span class='reward'>→ {e(c['rule_text'][h['rule']])}</span></li>"
                  for h in recent) or "<li>None yet.</li>"
    pages["forfeits.html"] = (page_head("forfeits.html") +
        f"<section><h2>Forfeit tally</h2><div class='scroll'><table><tr><th>Drafter</th>"
        f"<th class='num'>Forfeits copped</th></tr>{rows}</table></div></section>"
        f"<section><h2>Minor forfeits tracker</h2>{_grid(c, cfg['forfeits'], 'f')}</section>"
        f"<section><h2>Recent forfeits</h2><ul>{rec}</ul></section>" + foot)
    return pages
