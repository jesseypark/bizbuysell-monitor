# CLAUDE.md

## Before starting work

Always read the `/docs` folder first:
- `docs/PROJECT_MAP.md` — architecture, key files, how things connect
- `docs/DECISIONS.md` — non-obvious design choices and reasoning
- `docs/HANDOFF.md` — current project state, what's done, what's in progress

## Before ending a session

Update the `/docs` files to reflect any changes made during the session.

## Project overview

Business listing monitor — scrapes BusinessBroker.net (not BizBuySell, which blocks all automated access) for new business-for-sale listings in Colorado and Washington, filters by SDE/cash flow ($300k+), tracks seen listings locally, and appends new matches to a Google Sheet.

## Dev environment

- Python 3.9 (system), virtualenv in `venv/`
- Activate: `source venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run: `python monitor.py` (add `--debug` for HTML dumps)
- Test run scheduled via cron: `run_monitor.sh`

## Key env vars (.env)

- `GOOGLE_CREDENTIALS_FILE` — path to service account JSON
- `GOOGLE_SHEET_ID` — target Google Sheet

## Google Sheet

- ID: see `.env` file (`GOOGLE_SHEET_ID`)
- Columns: Date Found, State, City, Business Name, Asking Price, SDE, SDE Flag, URL, Industry
