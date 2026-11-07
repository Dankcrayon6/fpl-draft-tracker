# FPL Draft Round 2 — stats & forfeit tracker

Automatically tracks league 11214 on the FPL Draft site: standings, form, bench points,
transactions, and every **minor prize** and **minor forfeit** from the league rules.

**Dashboard:** https://dankcrayon6.github.io/fpl-draft-tracker/

## How it works
- Every morning (7:30am Brisbane) GitHub Actions runs `python -m tracker.main`.
- It pulls every finished gameweek from the draft site's data feed, recalculates the whole
  season, rebuilds `docs/index.html` (the dashboard) and `docs/summary.md` (a weekly
  write-up to paste into the group chat), and commits the result.
- Raw data for finished gameweeks is saved in `data/raw/`, so history is kept even if the feed changes.
- To run it now: **Actions → Update tracker → Run workflow**.

## Rule interpretations (agreed)
- **Starters** = the XI picked, before auto-subs. **Bench** = the 4 picked on the bench.
- Rules **stack** (a 20-point week also counts as 25 or less; 100 also counts as 80+).
- Each rule triggers at most once per drafter per gameweek.
- "Any player" rules (hattrick, own goal, 30+ player) and the "conceded 5+" rule only count
  players who **played and counted** — a starter who played, or a bench player who was subbed on.
  A bench hattrick that isn't subbed on therefore lands as the "12+ on the bench" forfeit instead.
- "Any squad player gets a red" covers the whole squad of 15, as the rule says.
- "Bench scores 20+" uses the players left on the bench after auto-subs.
- "First drafter to…" ties in the same gameweek are split.
- "50+ three gameweeks in a row" is awarded each time a fresh run of three completes.
- Missed penalties only count from GW10.

## Changing things
- Rule names, prize/forfeit text, league id, prize money: `config.yaml`.
- Rule logic: `tracker/rules.py` (one small function per rule, matched by id).
- Tests: `python tests/test_rules.py` (synthetic league that triggers every rule).

## Optional: post to Discord
Add a repository secret named `DISCORD_WEBHOOK` (Settings → Secrets and variables → Actions)
with a channel webhook URL. The summary posts once per new finished gameweek.
