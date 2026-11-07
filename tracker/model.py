"""Turn raw API responses into per-gameweek, per-drafter team sheets.

Terminology (agreed with the league):
  * starters  = the XI the drafter PICKED (positions 1-11), before auto-subs
  * bench     = positions 12-15 as picked
  * subbed on = a bench player brought into the XI by an automatic sub
  * counted   = a player whose points counted: a starter who played, or a bench
                player who was subbed on ("must have played")
"""
from dataclasses import dataclass, field

GK, DEF, MID, FWD = 1, 2, 3, 4
POS_NAME = {GK: "GK", DEF: "DEF", MID: "MID", FWD: "FWD"}


@dataclass
class FixtureLine:
    fixture: int
    minutes: int = 0
    goals: int = 0
    penalties_saved: int = 0
    team_conceded: int | None = None   # goals the player's club conceded in this fixture


@dataclass
class Player:
    id: int
    name: str
    etype: int
    team: int
    points: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    own_goals: int = 0
    penalties_saved: int = 0
    penalties_missed: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    fixtures: list = field(default_factory=list)   # list[FixtureLine]
    position: int = 0          # 1-15 slot in the drafter's picks
    subbed_on: bool = False
    subbed_off: bool = False

    @property
    def is_starter(self):
        return self.position <= 11

    @property
    def counted(self):
        if self.is_starter:
            return not self.subbed_off and self.minutes > 0
        return self.subbed_on

    @property
    def label(self):
        return f"{self.name} ({POS_NAME.get(self.etype, '?')})"


@dataclass
class TeamWeek:
    gw: int
    entry_id: int
    drafter: str
    team_name: str
    players: list            # list[Player], sorted by position
    official_points: int | None
    sub_warning: str | None = None

    @property
    def starters(self):
        return [p for p in self.players if p.is_starter]

    @property
    def bench(self):
        return [p for p in self.players if not p.is_starter]

    @property
    def counted(self):
        return [p for p in self.players if p.counted]

    @property
    def final_bench(self):
        """Bench players who stayed on the bench (were not subbed on)."""
        return [p for p in self.bench if not p.subbed_on]

    @property
    def computed_points(self):
        return sum(p.points for p in self.players
                   if (p.is_starter and not p.subbed_off) or p.subbed_on)

    @property
    def points(self):
        return self.official_points if self.official_points is not None else self.computed_points


# ---------------------------------------------------------------------------
def _explain_lines(explain):
    """Normalise the 'explain' block into [(fixture_id, {stat: value})].

    Draft API format: [[ [ {"stat": "minutes", "value": 90, ...}, ... ], fixture_id ], ...]
    Main FPL format:  [ {"fixture": id, "stats": [{"identifier": "minutes", "value": 90}]} ]
    """
    out = []
    for item in explain or []:
        if isinstance(item, dict):
            fx = item.get("fixture")
            stats = {s.get("identifier") or s.get("stat"): s.get("value", 0) for s in item.get("stats", [])}
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            rows, fx = item
            stats = {}
            for s in rows or []:
                key = s.get("stat") or s.get("identifier") or s.get("name")
                stats[key] = s.get("value", 0)
        else:
            continue
        out.append((fx, stats))
    return out


def build_players(bootstrap, live):
    """Return {element_id: Player} for one gameweek (without pick info)."""
    els = {e["id"]: e for e in bootstrap["elements"]}
    fixtures = {f["id"]: f for f in live.get("fixtures", []) or []}
    out = {}
    for sid, row in (live.get("elements") or {}).items():
        eid = int(sid)
        meta = els.get(eid, {})
        st = row.get("stats", {}) or {}
        p = Player(
            id=eid,
            name=meta.get("web_name", f"#{eid}"),
            etype=meta.get("element_type", 0),
            team=meta.get("team", 0),
            points=int(st.get("total_points", 0) or 0),
            minutes=int(st.get("minutes", 0) or 0),
            goals=int(st.get("goals_scored", 0) or 0),
            assists=int(st.get("assists", 0) or 0),
            own_goals=int(st.get("own_goals", 0) or 0),
            penalties_saved=int(st.get("penalties_saved", 0) or 0),
            penalties_missed=int(st.get("penalties_missed", 0) or 0),
            yellow_cards=int(st.get("yellow_cards", 0) or 0),
            red_cards=int(st.get("red_cards", 0) or 0),
        )
        for fx_id, stats in _explain_lines(row.get("explain")):
            fl = FixtureLine(
                fixture=fx_id,
                minutes=int(stats.get("minutes", 0) or 0),
                goals=int(stats.get("goals_scored", 0) or 0),
                penalties_saved=int(stats.get("penalties_saved", 0) or 0),
            )
            fx = fixtures.get(fx_id)
            if fx and fx.get("team_h_score") is not None and p.team:
                if fx.get("team_h") == p.team:
                    fl.team_conceded = fx.get("team_a_score")
                elif fx.get("team_a") == p.team:
                    fl.team_conceded = fx.get("team_h_score")
            p.fixtures.append(fl)
        out[eid] = p
    return out


def _auto_subs(players):
    """Fallback FPL auto-sub logic if the API gives no 'subs' list."""
    xi = [p for p in players if p.is_starter]
    bench = sorted([p for p in players if not p.is_starter], key=lambda p: p.position)
    mins = {GK: 1, DEF: 3, MID: 2, FWD: 1}
    subs = []
    for out_p in [p for p in xi if p.minutes == 0]:
        for b in bench:
            if b.subbed_on or b.minutes == 0:
                continue
            if (out_p.etype == GK) != (b.etype == GK):
                continue
            current = [p for p in xi if not p.subbed_off and p is not out_p] + [x for x in bench if x.subbed_on] + [b]
            if all(sum(1 for p in current if p.etype == t) >= n for t, n in mins.items()):
                b.subbed_on, out_p.subbed_off = True, True
                subs.append((b.id, out_p.id))
                break
    return subs


def build_teamweek(gw, entry_id, drafter, team_name, picks_json, players_by_id):
    import copy
    players = []
    for pk in picks_json.get("picks", []):
        base = players_by_id.get(pk["element"])
        p = copy.deepcopy(base) if base else Player(id=pk["element"], name=f"#{pk['element']}", etype=0, team=0)
        p.position = pk["position"]
        players.append(p)
    players.sort(key=lambda p: p.position)

    subs = picks_json.get("subs")
    if subs is None:
        subs = picks_json.get("automatic_subs")
    warning = None
    by_id = {p.id: p for p in players}
    if subs is not None:
        for s in subs:
            if s.get("event") not in (None, gw):
                continue
            pin, pout = by_id.get(s.get("element_in")), by_id.get(s.get("element_out"))
            if pin:
                pin.subbed_on = True
            if pout:
                pout.subbed_off = True
    else:
        _auto_subs(players)
        warning = "auto-subs computed locally (API gave no subs list)"

    hist = picks_json.get("entry_history") or {}
    official = hist.get("points")
    tw = TeamWeek(gw, entry_id, drafter, team_name, players,
                  int(official) if official is not None else None, warning)
    if official is not None and tw.computed_points != official:
        tw.sub_warning = (f"computed {tw.computed_points} pts vs official {official} "
                          f"(check subs / late corrections)")
    return tw
