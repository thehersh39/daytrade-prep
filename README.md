# daytrade-prep

Pulls Yahoo Finance data for the Morning Day-Trade Prep email every weekday before the open.

- `screen.py` builds `data.json`: prior-session levels, setups, premarket quotes, earnings this week, and stocks in play on news.
- `.github/workflows/screen.yml` runs it at 9:05 and 9:50 UTC on weekdays and commits the result.
- `status.json` shows when it last ran and what it found.

Run it by hand from the Actions tab → Morning screen → Run workflow.
