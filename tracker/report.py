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

    # per drafter per gameweek stat lines (players whose score went into the total)
    stat_rows = {d: {} for d in drafters}
    for gw in gws:
        for tw in teamweeks[gw]:
            xi = [p for p in tw.players if p.in_final_xi]
            stat_rows[tw.drafter][gw] = dict(
                pts=tw.points,
                goals=sum(p.goals for p in xi), xg=round(sum(p.xg for p in xi), 2),
                assists=sum(p.assists for p in xi), xa=round(sum(p.xa for p in xi), 2),
                cs=sum(p.clean_sheets for p in xi if p.etype in (1, 2)),
                dc=sum(p.dc_hits for p in xi), bonus=sum(p.bonus for p in xi),
                saves=sum(p.saves for p in xi), ps=sum(p.penalties_saved for p in xi),
                pm=sum(p.penalties_missed for p in xi), og=sum(p.own_goals for p in xi),
                yc=sum(p.yellow_cards for p in xi), rc=sum(p.red_cards for p in xi),
                zero=sum(1 for p in xi if p.points <= 0),
                bench=sum(p.points for p in tw.final_bench),
                subs=sum(1 for p in tw.players if p.subbed_on))

    latest = gws[-1] if gws else None
    latest_rows = sorted(teamweeks.get(latest, []), key=lambda t: -t.points) if latest else []

    hi = max(n_prize.values()) if n_prize else 0
    lo = min(n_prize.values()) if n_prize else 0
    return dict(cfg=cfg, league_name=league["league"].get("name", "FPL Draft"),
                drafters=drafters, order=order, teams={names[k]: v for k, v in teams.items()},
                tx={d: tx_counts.get(eid_by_name[d], 0) for d in drafters},
                gws=gws, pts=pts, total=total, bench=bench, grid=grid, hits=hits,
                n_prize=n_prize, n_forf=n_forf, money=money, latest=latest, latest_rows=latest_rows,
                stat_rows=stat_rows, current=current, current_done=current_done, warnings=warnings, now=now,
                most=[d for d in drafters if n_prize[d] == hi], least=[d for d in drafters if n_prize[d] == lo],
                rule_name={r["id"]: r["name"] for r in rules},
                rule_text={r["id"]: r.get("reward") or r.get("forfeit") for r in rules})


def build_waivers(tx_list, names, teamweeks, points_by_gw, el_names):
    """Accepted waivers / free-agent signings, with points gained and lost."""
    kinds = {"w": "Waiver", "f": "Free agent"}
    acc = [t for t in tx_list if t.get("result") in ("a", "accepted") and t.get("entry") in names]
    finished = sorted(points_by_gw)
    rows = []
    for t in acc:
        gw, pin, pout = t.get("event"), t.get("element_in"), t.get("element_out")
        d = names[t["entry"]]
        gained = 0
        for g in finished:
            if g < gw:
                continue
            for tw in teamweeks.get(g, []):
                if tw.drafter == d:
                    gained += sum(p.points for p in tw.players if p.id == pin and p.in_final_xi)
        lost = sum(points_by_gw[g].get(pout, 0) for g in finished if g >= gw)
        rows.append(dict(drafter=d, gw=gw, kind=kinds.get(t.get("kind"), t.get("kind") or "?"),
                         player_in=el_names.get(pin, f"#{pin}"), player_out=el_names.get(pout, f"#{pout}"),
                         gained=gained, lost=lost, scored=gw in points_by_gw or any(g >= gw for g in finished)))
    latest = max((r["gw"] for r in rows), default=None)
    return dict(rows=rows, latest=latest)


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
:root{--ink:#1d1630;--muted:#6b6380;--line:#e7e3ef;--bg:#faf9fc;--card:#fff;--accent:#c8312c;--header:#f06a63;
--good:#0f7a4a;--goodbg:#e3f5ec;--bad:#b3261e;--badbg:#fbe6e4;}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
color:var(--ink);background:var(--bg)}
header{background:var(--header);color:#fff;padding:20px 16px}
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
td.zero{color:#c9c3d6}tr.total td{border-top:2px solid var(--line);background:var(--bg)}
.picker{display:block;margin:0 0 12px;font-weight:600;font-size:14px}
.picker select{margin-left:6px;font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:#fff}
th.sortable{cursor:pointer;user-select:none}th.sorted{color:var(--accent)}
table.stats th:first-child,table.stats td:first-child{position:sticky;left:0;background:var(--card);z-index:1}
td.lead{background:var(--goodbg);color:var(--good);font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.two section{margin:0 0 16px}
@media(max-width:760px){.two{grid-template-columns:1fr}}
.who{font-size:15px!important}.moves{list-style:none;padding:0;margin:6px 0 0}.moves li{margin:4px 0}
.in{color:var(--good);font-weight:600}.out{color:var(--bad);margin-left:6px}
tr.drow{cursor:pointer}tr.drow:hover td{background:var(--bg)}.dname{color:var(--accent)}
tr.dmore>td{background:var(--bg);padding:8px 10px 12px}table.sub{background:var(--card);border:1px solid var(--line);border-radius:8px}
.bgimg{position:sticky;top:0;height:100vh;margin-bottom:-100vh;z-index:0;display:flex;background:#111}
body.has-bg main{position:relative;z-index:1}
.bgimg>div{flex:1;background-size:cover}
body.has-bg main{padding-top:min(56vh,500px)}
.bgimg::after{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(rgba(20,10,10,.05),rgba(20,10,10,.45))}
body.has-bg{background:#111}body.has-bg section{background:rgba(255,255,255,.94);backdrop-filter:blur(3px)}
body.has-bg main>p.reward{color:#fff}
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
    head = "".join(f"<th class='num'>{e(d)}</th>" for d in c["order"])
    body = []
    totals = {d: 0 for d in c["order"]}
    for r in rules:
        cells = []
        for d in c["order"]:
            gws = c["grid"][r["id"]][d]
            totals[d] += len(gws)
            tip = "GW " + ", ".join(str(g) for g in gws)
            cells.append(f"<td class='num'><span class='chip {cls}' title='{tip}'>{len(gws)}</span></td>"
                         if gws else "<td class='num zero'>–</td>")
        body.append(f"<tr><td class='wrap'>{e(r['name'])}<br><span class='reward'>"
                    f"{e(r.get('reward') or r.get('forfeit'))}</span></td>{''.join(cells)}</tr>")
    tot = "".join(f"<td class='num'><b>{totals[d]}</b></td>" for d in c["order"])
    return (f"<div class='scroll'><table><tr><th>Rule</th>{head}</tr>{''.join(body)}"
            f"<tr class='total'><td><b>Total</b></td>{tot}</tr></table></div>"
            f"<p class='reward'>On a computer, hover over a number to see which gameweeks.</p>")


PAGES = [("index.html", "Gameweek Summary"), ("prizes.html", "Minor Prizes"),
         ("forfeits.html", "Minor Forfeits"), ("stats.html", "Stats"), ("waivers.html", "Waivers")]

STAT_COLS = [  # key, header, tooltip
    ("pts", "Pts", "Points"), ("avg", "Avg", "Average points per gameweek"),
    ("best", "Best GW", "Highest gameweek score"), ("worst", "Worst GW", "Lowest gameweek score"),
    ("goals", "G", "Goals"), ("xg", "xG", "Expected goals"), ("assists", "A", "Assists"),
    ("xa", "xA", "Expected assists"), ("cs", "CS", "Clean sheets (GK/DEF)"),
    ("dc", "DC", "Defensive contribution thresholds reached"), ("bonus", "Bonus", "Bonus points"),
    ("saves", "Saves", "Goalkeeper saves"), ("ps", "Pen saves", "Penalties saved"),
    ("pm", "Pen misses", "Penalties missed"), ("og", "OG", "Own goals"),
    ("yc", "YC", "Yellow cards"), ("rc", "RC", "Red cards"),
    ("zero", "Zero pts", "Players in the final XI who scored 0 or less"),
    ("bench", "Bench pts", "Points left on the bench"), ("subs", "Auto-subs", "Bench players auto-subbed on"),
]

STATS_JS = r"""
const D = JSON.parse(document.getElementById('statdata').textContent);
const sel = document.getElementById('gwsel'), tbody = document.getElementById('stbody');
let sortKey = 'pts', sortDir = -1;
function gwsFor(v){ if(v==='all') return D.gws; if(v==='last5') return D.gws.slice(-5); return [Number(v)]; }
function calc(){
  const gws = gwsFor(sel.value);
  return D.drafters.map(d => {
    const r = {name:d}; D.cols.forEach(c => r[c]=0);
    const pts = [];
    gws.forEach(g => { const s = (D.rows[d]||{})[g]; if(!s) return; pts.push(s.pts);
      for (const k in s) r[k] += s[k]; });
    r.avg = pts.length ? r.pts/pts.length : 0;
    r.best = pts.length ? Math.max(...pts) : 0; r.worst = pts.length ? Math.min(...pts) : 0;
    return r; });
}
function fmt(k,v){ return (k==='avg'||k==='xg'||k==='xa') ? v.toFixed(1) : v; }
function render(){
  const rows = calc().sort((a,b)=> sortDir*((a[sortKey]-b[sortKey]) || (a.name<b.name?1:-1)));
  const max = {}; D.cols.forEach(c => max[c] = Math.max(...rows.map(r=>r[c])));
  tbody.innerHTML = rows.map(r => '<tr><td><b>'+r.name+'</b></td>' + D.cols.map(c =>
     '<td class="num'+(r[c]===max[c] && max[c]>0 ? ' lead':'')+'">'+fmt(c,r[c])+'</td>').join('') + '</tr>').join('');
  document.querySelectorAll('th[data-k]').forEach(th => th.classList.toggle('sorted', th.dataset.k===sortKey));
}
document.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
  if (sortKey === th.dataset.k) sortDir = -sortDir; else { sortKey = th.dataset.k; sortDir = -1; }
  render(); }));
sel.addEventListener('change', render); render();
"""


def render_html(c):
    cfg, gw = c["cfg"], c["latest"]
    status = (f"Updated through GW{gw}" if gw else "No finished gameweeks yet")
    if c["current"] and not c["current_done"] and c["current"] != gw:
        status += f" · GW{c['current']} in progress"
    bgs = {f"{k}.html" if not k.endswith(".html") else k: v
           for k, v in (cfg.get("backgrounds") or {}).items() if v}
    bgs = {k: (v if isinstance(v, list) else [v]) for k, v in bgs.items()}

    def page_head(active):
        tabs = "".join(f"<a href='{f}' class='{'on' if f == active else ''}'>{e(t)}</a>" for f, t in PAGES)
        bg = ""
        if bgs.get(active):
            bg = "<div class='bgimg'>" + "".join(
                f"<div style=\"background-image:url('{e(u.split()[0])}');background-position:"
                f"{e(' '.join(u.split()[1:]) or 'center top')}\"></div>" for u in bgs[active]) + "</div>"
        return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{e(c['league_name'])} tracker</title><style>{CSS}</style></head>"
                f"<body{' class=has-bg' if bg else ''}>"
                f"<header><h1>{e(c['league_name'])}</h1><p>{status} · refreshed "
                f"{c['now'].strftime('%a %d %b %Y, %I:%M %p')} Brisbane</p></header>"
                f"<nav>{tabs}</nav>{bg}<main>")
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

    # --- Stats page
    import json as _json
    cols = [k for k, _, _ in STAT_COLS]
    data = {"gws": c["gws"], "drafters": [e(d) for d in c["drafters"]],
            "rows": {e(d): v for d, v in c["stat_rows"].items()}, "cols": cols}
    data_json = _json.dumps(data).replace("</", "<\\/")
    opts = "<option value='all'>Whole season</option><option value='last5'>Last 5 gameweeks</option>" + "".join(
        f"<option value='{g}'>Gameweek {g}</option>" for g in reversed(c["gws"]))
    ths = "".join(f"<th class='num sortable' data-k='{k}' title='{e(t)}'>{e(h)}</th>" for k, h, t in STAT_COLS)
    pages["stats.html"] = (page_head("stats.html") +
        f"<section><h2>Stats</h2><label class='picker'>Show stats for "
        f"<select id='gwsel'>{opts}</select></label>"
        f"<div class='scroll'><table class='stats'><thead><tr><th>Drafter</th>{ths}</tr></thead>"
        f"<tbody id='stbody'></tbody></table></div>"
        f"<p class='reward'>Counts players whose score went into the team total (the XI after auto-subs). "
        f"Tap a column heading to sort. Green = top of that column. DC = defensive contribution thresholds hit.</p>"
        f"</section><script type='application/json' id='statdata'>{data_json}</script>"
        f"<script>{STATS_JS}</script>" + foot)

    # --- Waivers page
    w = c.get("waivers") or {"rows": [], "latest": None}
    parts = [page_head("waivers.html")]
    if w["latest"]:
        week = [r for r in w["rows"] if r["gw"] == w["latest"]]
        by_d = {}
        for r in week:
            by_d.setdefault(r["drafter"], []).append(r)
        cards = []
        for d in c["order"]:
            if d not in by_d:
                continue
            items = "".join(f"<li><span class='in'>▲ {e(r['player_in'])}</span> "
                            f"<span class='out'>▼ {e(r['player_out'])}</span> "
                            f"<span class='reward'>{e(r['kind'])}</span></li>" for r in by_d[d])
            cards.append(f"<div class='card'><b class='who'>{e(d)}</b><ul class='moves'>{items}</ul></div>")
        quiet = [d for d in c["order"] if d not in by_d]
        parts.append(f"<section><h2>GW{w['latest']} successful waivers</h2>"
                     f"<div class='cards'>{''.join(cards) or '<p>None.</p>'}</div>"
                     + (f"<p class='reward'>No moves: {e(', '.join(quiet))}</p>" if quiet else "")
                     + "</section>")
    counted = [r for r in w["rows"] if any(g >= r["gw"] for g in c["gws"])]
    def tbl(title, key, desc, cols):
        top = sorted(counted, key=lambda r: (-r[key], r["gw"]))[:10]
        body = "".join(f"<tr><td>{i}</td><td><b>{e(r['drafter'])}</b></td><td>{e(r[cols])}</td>"
                       f"<td class='num'>GW{r['gw']}</td><td class='num'><b>{r[key]}</b></td></tr>"
                       for i, r in enumerate(top, 1)) or "<tr><td colspan='5'>No data yet.</td></tr>"
        return (f"<section><h2>{title}</h2><p class='reward'>{desc}</p><div class='scroll'><table>"
                f"<tr><th>#</th><th>Drafter</th><th>Player</th><th class='num'>Moved</th>"
                f"<th class='num'>Pts</th></tr>{body}</table></div></section>")
    parts.append("<div class='two'>" +
                 tbl("Most points gained", "gained", "Points a signing has scored for the drafter since "
                     "joining (only weeks they were in the XI after auto-subs).", "player_in") +
                 tbl("Most points lost", "lost", "Points a dropped player has scored since being let go, "
                     "wherever they've played.", "player_out") + "</div>")
    net = {d: (sum(r["gained"] for r in counted if r["drafter"] == d),
               sum(r["lost"] for r in counted if r["drafter"] == d),
               sum(1 for r in w["rows"] if r["drafter"] == d)) for d in c["drafters"]}
    played = set(c["gws"])
    def sgn(n):
        return format(n, "+d") if n else "0"
    nrows = []
    for i, d in enumerate(sorted(c["drafters"], key=lambda d: -(net[d][0] - net[d][1]))):
        g, l, m = net[d]
        moves = sorted([r for r in w["rows"] if r["drafter"] == d], key=lambda r: -r["gw"])
        det = []
        for r in moves:
            done = any(x >= r["gw"] for x in played)
            gp, lp = (r["gained"], r["lost"]) if done else ("–", "–")
            nt = sgn(r["gained"] - r["lost"]) if done else "–"
            det.append(f"<tr><td class='num'>GW{r['gw']}</td><td><span class='in'>▲ {e(r['player_in'])}</span></td>"
                       f"<td class='num'>{gp}</td><td><span class='out'>▼ {e(r['player_out'])}</span></td>"
                       f"<td class='num'>{lp}</td><td class='num'><b>{nt}</b></td>"
                       f"<td class='reward'>{e(r['kind'])}{'' if done else ' · not played yet'}</td></tr>")
        detail = ("<table class='sub'><tr><th class='num'>GW</th><th>In</th><th class='num'>Gained</th>"
                  "<th>Out</th><th class='num'>Lost</th><th class='num'>Net</th><th></th></tr>"
                  + ("".join(det) or "<tr><td colspan='7'>No moves yet.</td></tr>") + "</table>")
        nrows.append(f"<tr class='drow' data-i='{i}'><td><b class='dname'>▸ {e(d)}</b></td><td class='num'>{m}</td>"
                     f"<td class='num'>{g}</td><td class='num'>{l}</td><td class='num'><b>{sgn(g - l)}</b></td></tr>"
                     f"<tr class='dmore' id='dm{i}' hidden><td colspan='5'>{detail}</td></tr>")
    parts.append("<section><h2>Waiver balance by drafter</h2><p class='reward'>Tap a drafter to see each move.</p>"
                 "<div class='scroll'><table><tr><th>Drafter</th>"
                 "<th class='num'>Moves</th><th class='num'>Gained</th><th class='num'>Lost</th>"
                 f"<th class='num'>Net</th></tr>{''.join(nrows)}</table></div></section>"
                 "<script>document.querySelectorAll('tr.drow').forEach(r=>r.addEventListener('click',()=>{"
                 "const m=document.getElementById('dm'+r.dataset.i);m.hidden=!m.hidden;"
                 "const n=r.querySelector('.dname');n.textContent=(m.hidden?'▸ ':'▾ ')+n.textContent.slice(2);}));</script>")
    pages["waivers.html"] = "".join(parts) + foot
    return pages
