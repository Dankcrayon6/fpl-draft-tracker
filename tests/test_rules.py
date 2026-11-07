"""End-to-end test on synthetic data: python tests/test_rules.py"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import make_fixtures  # noqa: E402
from tracker import main  # noqa: E402

EXPECTED = {
    ("p_first_100", "Aidan", 1), ("p_first_100", "Bronson", 1),
    ("p_first_30_player", "Aidan", 1), ("p_first_30_player", "Bronson", 1),
    ("p_80_plus", "Aidan", 1), ("p_80_plus", "Bronson", 1), ("p_80_plus", "Rory", 3),
    ("p_hattrick", "Aidan", 1), ("p_gk_assist", "Aidan", 1),
    ("p_all_starters_gt3", "Rory", 1), ("p_all_starters_gt2", "Rory", 1),
    ("p_def_2_goals", "Rory", 1), ("p_gk_2_pen_saves", "Rory", 1),
    ("p_first_69", "Julius", 2),
    ("p_bench_12_subbed", "Dilan", 2),
    ("p_50_three_in_row", "Harry", 3),
    ("p_def_35", "Rory", 3), ("p_mid_30", "Rory", 3), ("p_fwd_25", "Rory", 3),
    ("p_three_12s", "Rory", 3),  # 13, 13 FWD... and DEFs 9 -> only 2; see check below
    ("f_three_zero", "Campbell", 2), ("f_two_zero", "Campbell", 2),
    ("f_four_carded", "Campbell", 2), ("f_two_reds", "Campbell", 2), ("f_gk_red", "Campbell", 2),
    ("f_squad_red", "Campbell", 2),
    ("f_bench_12_not_subbed", "Dilan", 2), ("f_bench_20", "Dilan", 2),
    ("f_conceded_5", "Jono", 3), ("f_own_goal", "Jono", 3),
    ("f_20_or_less", "Julius", 3), ("f_25_or_less", "Julius", 3),
    ("f_both_gk_1", "Rory", 3), ("f_both_gk_1", "Julius", 3),
    ("p_fwd_25", "Aidan", 1), ("p_fwd_25", "Bronson", 1), ("p_mid_30", "Aidan", 1), ("p_mid_30", "Julius", 2),
}
# Rory GW3 has only two 12+ starters (13, 13), so three_12s must NOT fire:
EXPECTED.discard(("p_three_12s", "Rory", 3))

make_fixtures.main()
with tempfile.TemporaryDirectory() as out:
    ctx = main.run(offline_dir=os.path.join(HERE, "fixtures"), out_dir=out)
    got = {(h["rule"], h["drafter"], h["gw"]) for h in ctx["hits"]}
    missing, extra = EXPECTED - got, got - EXPECTED
    for m in sorted(missing):
        print("MISSING", m)
    for x in sorted(extra):
        print("EXTRA  ", x)
    shares = {(h["rule"], h["drafter"]): h["share"] for h in ctx["hits"] if h["rule"] == "p_first_100"}
    assert shares == {("p_first_100", "Aidan"): 0.5, ("p_first_100", "Bronson"): 0.5}, shares
    assert ctx["money"]["Aidan"] == 20 and ctx["money"]["Bronson"] == 20, ctx["money"]
    assert not missing and not extra
    assert not [w for w in ctx["warnings"] if "computed" in w], ctx["warnings"]
    html = open(os.path.join(out, "index.html")).read()
    assert "Minor forfeits tracker" in html and "GW3 wrap" in html
print("ALL RULE TESTS PASSED")
