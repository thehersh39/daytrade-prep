# daytrade-prep

Pulls Yahoo Finance data for the Morning Day-Trade Prep email every weekday before the open.

- `screen.py` builds `data.json`: prior-session levels, setups, premarket quotes, earnings this week, and stocks in play on news.
- `.github/workflows/screen.yml` runs it every 20 minutes from 08:07 to 10:47 UTC on weekdays (plus an evening backup) and commits the result.
- `status.json` shows when it last ran and what it found.

Run it by hand from the Actions tab → Morning screen → Run workflow.
- `build.py` + `template.txt` turn `data.json` into `email.html`, `email.txt` and `index.html` in the same workflow run. The Claude scheduled task at 5:17 AM CT just sends the email and refreshes the page.
