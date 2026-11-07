"""Generate a synthetic 3-gameweek league in the draft API's JSON shape.

Every rule is triggered by a specific drafter/gameweek so test_rules.py can
check the engine end to end.
"""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "fixtures")
NAMES = ["aidan", "Bronson", "Campbell", "dilan", "Harry", "Jono", "Julius", "Rory"]
# slot -> element_type : XI = GK, 4 DEF, 4 MID, 2 FWD ; bench = GK, DEF, MID, FWD
ETYPE = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 1, 2, 3, 4]
BASE_PTS = [2, 1, 6, 2, 3, 5, 2, 8, 2, 6, 3, 1, 2, 3, 1]
SPECIAL_TEAM = {}  # element -> team


def eid(entry, slot):  # slot 1..15
    return entry * 15 + slot


def blank(entry, slot):
    return dict(total_points=BASE_PTS[slot - 1], minutes=90, goals_scored=0, assists=0, own_goals=0,
                penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0)


def scenario(entry, gw, s, subs):
    """Mutate slot stats s[slot] and subs list for (entry index, gw)."""
    n = NAMES[entry]
    if gw == 1 and n in ("aidan", "Bronson"):           # both hit 100 in GW1 -> tie
        s[10]["total_points"] = 66                       # 40 + 60ish
        if n == "aidan":
            s[10].update(total_points=36, goals_scored=3)  # 30+ player + hattrick
            s[8]["total_points"] = 38
            s[1]["assists"] = 1                          # GK assist
    if gw == 2 and n == "Campbell":
        for k in (2, 3, 4):
            s[k]["total_points"] = 0                     # 3 zero starters
        for k in (5, 6, 7, 8):
            s[k]["yellow_cards"] = 1                     # 4 carded
        s[1]["red_cards"] = 1; s[9]["red_cards"] = 1     # GK red + 2 starter reds
    if gw == 2 and n == "dilan":
        s[7].update(minutes=0, total_points=0)           # MID starter didn't play
        s[14]["total_points"] = 13                       # bench MID subbed on, 12+
        s[15]["total_points"] = 12                       # bench FWD, 12+ not subbed
        s[13]["total_points"] = 9                        # bench total 1+9+12=22 -> 20+
        subs.append({"element_in": eid(entry, 14), "element_out": eid(entry, 7), "event": 2})
    if n == "Harry":                                     # 50+ GW1-3 -> streak at GW3
        s[8]["total_points"] = 20
    if gw == 3 and n == "Jono":
        SPECIAL_TEAM[eid(entry, 3)] = 21                 # DEF whose team lost 0-5
        s[4]["own_goals"] = 1
        s[6]["penalties_missed"] = 1                     # GW3 < 10: must NOT trigger
    if gw == 2 and n == "Julius":
        s[8]["total_points"] = 37                        # 40 - 8 + 37 = 69
    if gw == 3 and n == "Julius":
        for k in range(1, 12):
            s[k]["total_points"] = 1                     # 11 pts -> <=20 and <=25
    if gw == 3 and n == "Rory":
        s[1]["total_points"] = 0; s[12]["total_points"] = 1   # both GKs <=1 -> but GK starter 0...
        s[1]["total_points"] = 1
        for k in (2, 3, 4, 5):
            s[k]["total_points"] = 9                     # DEF 36
        for k in (6, 7, 8, 9):
            s[k]["total_points"] = 8                     # MID 32
        s[10]["total_points"] = 13; s[11]["total_points"] = 13  # FWD 26
        # every starter >3 fails because GK has 1 -> fine, tested elsewhere
    if gw == 1 and n == "Rory":
        for k in range(1, 12):
            s[k]["total_points"] = 4                     # every starter >3 (and >2)
        s[2]["goals_scored"] = 2                         # DEF 2 goals
        s[1]["penalties_saved"] = 2                      # GK 2 pen saves same game


def main():
    os.makedirs(OUT, exist_ok=True)
    def w(name, obj):
        json.dump(obj, open(os.path.join(OUT, name + ".json"), "w"))

    lives = {}
    picks = {}
    for gw in (1, 2, 3):
        elements = {}
        for entry in range(8):
            s = {slot: blank(entry, slot) for slot in range(1, 16)}
            subs = []
            scenario(entry, gw, s, subs)
            for slot in range(1, 16):
                e = eid(entry, slot)
                team = SPECIAL_TEAM.get(e, (e - 1) % 20 + 1)
                fx = 100 + (team + 1) // 2 if team <= 20 else 199
                st = s[slot]
                explain = [[[{"name": "Minutes", "stat": "minutes", "value": st["minutes"], "points": 2},
                             {"name": "Goals", "stat": "goals_scored", "value": st["goals_scored"], "points": 0},
                             {"name": "Pen saves", "stat": "penalties_saved", "value": st["penalties_saved"], "points": 0}],
                            fx]]
                elements[str(e)] = {"stats": st, "explain": explain}
            # official points = XI minus subbed-off plus subbed-on
            out_ids = {x["element_out"] for x in subs}; in_ids = {x["element_in"] for x in subs}
            pts = sum(s[k]["total_points"] for k in range(1, 12) if eid(entry, k) not in out_ids)
            pts += sum(s[k]["total_points"] for k in range(12, 16) if eid(entry, k) in in_ids)
            picks[(entry, gw)] = {"picks": [{"element": eid(entry, k), "position": k} for k in range(1, 16)],
                                  "entry_history": {"points": pts, "event": gw}, "subs": subs}
        fixtures = [{"id": 100 + i, "team_h": 2 * i - 1, "team_a": 2 * i, "team_h_score": 1, "team_a_score": 1,
                     "event": gw, "finished": True} for i in range(1, 11)]
        fixtures.append({"id": 199, "team_h": 21, "team_a": 22, "team_h_score": 0,
                         "team_a_score": 5 if gw == 3 else 0, "event": gw, "finished": True})
        lives[gw] = {"elements": elements, "fixtures": fixtures}

    all_ids = [eid(e, k) for e in range(8) for k in range(1, 16)]
    w("bootstrap-static", {
        "elements": [{"id": i, "web_name": f"P{i}", "element_type": ETYPE[(i - 1) % 15],
                      "team": SPECIAL_TEAM.get(i, (i - 1) % 20 + 1)} for i in all_ids],
        "events": {"current": 3, "data": [{"id": g, "finished": True} for g in (1, 2, 3)] +
                   [{"id": 4, "finished": False}]}})
    w("game", {"current_event": 3, "current_event_finished": True})
    w("league__11214__details", {"league": {"id": 11214, "name": "FPL Draft Round 2 (TEST DATA)"},
        "league_entries": [{"id": 900 + e, "entry_id": 5000 + e, "entry_name": f"Team {NAMES[e]}",
                            "player_first_name": NAMES[e], "player_last_name": "X"} for e in range(8)],
        "standings": []})
    w("draft__league__11214__transactions", {"transactions": [
        {"entry": 5000, "result": "a", "event": 2, "kind": "w", "element_in": 10, "element_out": 30},
        {"entry": 5000, "result": "di", "event": 2, "kind": "w", "element_in": 11, "element_out": 31},
        {"entry": 5003, "result": "a", "event": 3, "kind": "f", "element_in": 55, "element_out": 8}]})
    for gw, lv in lives.items():
        w(f"event__{gw}__live", lv)
    for (entry, gw), pj in picks.items():
        w(f"entry__{5000 + entry}__event__{gw}", pj)


if __name__ == "__main__":
    main()
