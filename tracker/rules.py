"""Minor prizes and minor forfeits.

Each weekly rule takes a TeamWeek and returns a short detail string when it is
triggered, or None. Rules stack (e.g. a 20-point week triggers both the
"20 or less" and "25 or less" forfeits) and each rule can trigger at most once
per drafter per gameweek.
"""
from .model import GK, DEF, MID, FWD


def _names(ps):
    return ", ".join(f"{p.name} {p.points}" for p in ps)


# ---------------------------------------------------------------- prizes ---
def p_first_100(tw, cfg):
    return f"{tw.points} pts" if tw.points >= 100 else None


def p_first_30_player(tw, cfg):
    hit = [p for p in tw.counted if p.points >= 30]
    return _names(hit) if hit else None


def p_first_69(tw, cfg):
    return "69 pts. Nice." if tw.points == 69 else None


def p_gk_2_pen_saves(tw, cfg):
    for p in tw.counted:
        if p.etype != GK:
            continue
        if p.fixtures:
            if any(f.penalties_saved >= 2 for f in p.fixtures):
                return f"{p.name} saved 2 pens in one game"
        elif p.penalties_saved >= 2:
            return f"{p.name} saved {p.penalties_saved} pens"
    return None


def p_three_12s(tw, cfg):
    hit = [p for p in tw.starters if p.points >= 12]
    return _names(hit) if len(hit) >= 3 else None


def p_bench_12_subbed(tw, cfg):
    hit = [p for p in tw.bench if p.subbed_on and p.points >= 12]
    return _names(hit) if hit else None


def p_all_starters_gt3(tw, cfg):
    return "all XI scored 4+" if tw.starters and all(p.points > 3 for p in tw.starters) else None


def p_all_starters_gt2(tw, cfg):
    return "all XI scored 3+" if tw.starters and all(p.points > 2 for p in tw.starters) else None


def _line_total(tw, etype, threshold, label):
    ps = [p for p in tw.starters if p.etype == etype]
    tot = sum(p.points for p in ps)
    return f"{label} {tot} pts ({_names(ps)})" if tot >= threshold else None


def p_fwd_25(tw, cfg):
    return _line_total(tw, FWD, 25, "FWDs")


def p_mid_30(tw, cfg):
    return _line_total(tw, MID, 30, "MIDs")


def p_def_35(tw, cfg):
    return _line_total(tw, DEF, 35, "DEFs")


def p_80_plus(tw, cfg):
    return f"{tw.points} pts" if tw.points >= 80 else None


def p_hattrick(tw, cfg):
    for p in tw.counted:
        if p.fixtures:
            if any(f.goals >= 3 for f in p.fixtures):
                return f"{p.name} hattrick"
        elif p.goals >= 3:
            return f"{p.name} {p.goals} goals"
    return None


def p_gk_assist(tw, cfg):
    hit = [p for p in tw.counted if p.etype == GK and p.assists >= 1]
    return ", ".join(f"{p.name} assist" for p in hit) if hit else None


def p_def_2_goals(tw, cfg):
    hit = [p for p in tw.counted if p.etype == DEF and p.goals >= 2]
    return ", ".join(f"{p.name} {p.goals} goals" for p in hit) if hit else None


# -------------------------------------------------------------- forfeits ---
def f_two_reds(tw, cfg):
    hit = [p for p in tw.starters if p.red_cards >= 1]
    return ", ".join(p.name for p in hit) + " sent off" if len(hit) >= 2 else None


def f_20_or_less(tw, cfg):
    return f"{tw.points} pts" if tw.points <= 20 else None


def f_25_or_less(tw, cfg):
    return f"{tw.points} pts" if tw.points <= 25 else None


def f_bench_12_not_subbed(tw, cfg):
    hit = [p for p in tw.bench if not p.subbed_on and p.points >= 12]
    return _names(hit) + " left on bench" if hit else None


def f_bench_20(tw, cfg):
    tot = sum(p.points for p in tw.final_bench)
    return f"bench {tot} pts ({_names(tw.final_bench)})" if tot >= 20 else None


def f_both_gk_1(tw, cfg):
    gks = [p for p in tw.players if p.etype == GK]
    return _names(gks) if len(gks) >= 2 and all(p.points <= 1 for p in gks) else None


def f_gk_red(tw, cfg):
    hit = [p for p in tw.starters if p.etype == GK and p.red_cards >= 1]
    return f"{hit[0].name} sent off" if hit else None


def _zeros(tw):
    return [p for p in tw.starters if not p.subbed_off and p.points <= 0]


def f_three_zero(tw, cfg):
    z = _zeros(tw)
    return _names(z) if len(z) >= 3 else None


def f_two_zero(tw, cfg):
    z = _zeros(tw)
    return _names(z) if len(z) >= 2 else None


def f_four_carded(tw, cfg):
    hit = [p for p in tw.starters if p.yellow_cards + p.red_cards >= 1]
    return f"{len(hit)} carded: " + ", ".join(p.name for p in hit) if len(hit) >= 4 else None


def f_conceded_5(tw, cfg):
    hits = []
    for p in tw.counted:
        if p.etype not in (GK, DEF):
            continue
        for f in p.fixtures:
            if f.minutes > 0 and f.team_conceded is not None and f.team_conceded >= 5:
                hits.append(f"{p.name} (conceded {f.team_conceded})")
                break
    return ", ".join(hits) if hits else None


def f_squad_red(tw, cfg):
    hit = [p for p in tw.players if p.etype != GK and p.red_cards >= 1]
    return ", ".join(p.name for p in hit) + " sent off" if hit else None


def f_own_goal(tw, cfg):
    hit = [p for p in tw.counted if p.own_goals >= 1]
    return ", ".join(f"{p.name} OG" for p in hit) if hit else None


def f_missed_pen(tw, cfg):
    if tw.gw < cfg.get("missed_pen_from_gw", 10):
        return None
    hit = [p for p in tw.starters if p.penalties_missed >= 1]
    return ", ".join(f"{p.name} missed pen" for p in hit) if hit else None


WEEKLY = {name: fn for name, fn in globals().items()
          if callable(fn) and (name.startswith("p_") or name.startswith("f_"))}


# ------------------------------------------------------------ evaluation ---
def evaluate(teamweeks, cfg):
    """teamweeks: {gw: [TeamWeek]} for finished gameweeks.

    Returns a list of hit dicts: {kind, rule, gw, entry_id, drafter, detail, share}
    """
    hits = []
    rule_cfg = {r["id"]: r for r in cfg["prizes"]}
    rule_cfg.update({r["id"]: r for r in cfg["forfeits"]})

    for rid, rc in rule_cfg.items():
        if rid == "p_50_three_in_row":
            continue
        fn = WEEKLY.get(rid)
        if fn is None:
            raise KeyError(f"No logic for rule {rid}")
        kind = "prize" if rid.startswith("p_") else "forfeit"
        rule_hits = []
        for gw in sorted(teamweeks):
            for tw in teamweeks[gw]:
                d = fn(tw, cfg)
                if d:
                    rule_hits.append(dict(kind=kind, rule=rid, gw=gw, entry_id=tw.entry_id,
                                          drafter=tw.drafter, detail=d, share=1.0))
        if rc.get("first_only") and rule_hits:
            first_gw = min(h["gw"] for h in rule_hits)
            rule_hits = [h for h in rule_hits if h["gw"] == first_gw]
            for h in rule_hits:
                h["share"] = 1.0 / len(rule_hits)
                if len(rule_hits) > 1:
                    h["detail"] += f" (tie — split {len(rule_hits)} ways)"
        hits.extend(rule_hits)

    # 50+ three gameweeks in a row: awarded each time a fresh run of 3 completes
    # (GW a, a+1, a+2 -> award at a+2; the count resets after each award).
    by_entry = {}
    for gw in sorted(teamweeks):
        for tw in teamweeks[gw]:
            by_entry.setdefault(tw.entry_id, []).append(tw)
    for eid, tws in by_entry.items():
        run, prev_gw = 0, None
        for tw in tws:
            if tw.points >= 50:
                run = run + 1 if prev_gw == tw.gw - 1 else 1
            else:
                run = 0
            prev_gw = tw.gw
            if run == 3:
                hits.append(dict(kind="prize", rule="p_50_three_in_row", gw=tw.gw, entry_id=eid,
                                 drafter=tw.drafter, detail=f"GW{tw.gw-2}-{tw.gw} all 50+", share=1.0))
                run = 0
    hits.sort(key=lambda h: (h["gw"], h["kind"], h["rule"], h["drafter"]))
    return hits
