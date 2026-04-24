# Handoff — Current State

## What's complete

- **Scraping**: working. Uses BusinessBroker.net via curl_cffi. Extracts listings from search results cards. Tested and producing results.
- **Industry classification**: working. Keyword-based classifier maps business names to canonical industries. Persistent cache in `industries.json`.
- **Google Sheets integration**: working. Service account auth connects, headers written, rows appended. Columns: Date Found, State, City, Business Name, Asking Price, SDE, Revenue, URL, Industry, Score, Rank.
- **Hard filters**: working. Rejects excluded industries, CF < $300k, asking > $5M, missing financials.
- **Scoring system**: working. 100-point scale across deal economics (50pts), business quality (30pts), and description keywords (20pts). Outputs Score + Rank (A/B/C/D) columns.
- **Detail page scraping**: implemented. Fetches detail pages only for listings passing hard filters to extract description, years established, and employee count for scoring.
- **Seen-listings tracking**: working. JSON file persists across runs, deduplicates correctly.
- **Zero-results warning**: implemented. Writes warning row to sheet if a state that previously had results returns zero.
- **Logging**: working. Dual output to console + `monitor.log` file. Guard against duplicate handlers.
- **Cron**: installed. Runs weekdays 8am-6pm Mountain (`0 8-18 * * 1-5`). Verified working 2026-04-23.
- **GitHub repo**: public at `jesseypark/bizbuysell-monitor`. Sensitive data scrubbed.
- **Project scaffolding**: `.env`, `.gitignore`, `requirements.txt`, `README.md` all current.

## What's not yet done

- **Notifications**: no automated notifications on new matches. Considered email (Gmail MCP), push (Claude), macOS native, and Slack. Deferred for now.
- **_scraper tab in Google Sheet**: leftover test tab from IMPORTHTML attempt. Contains #REF! errors. Should be deleted manually.
- **Cleanup venv**: extra packages from debugging are installed but not needed. `pip install -r requirements.txt` in a fresh venv would be cleaner.

## Known limitations

- **Not BizBuySell**: uses BusinessBroker.net instead. Some BizBuySell-exclusive listings won't appear.
- **Industry classification is keyword-based**: ~30% of listings get "Other" when the business name doesn't contain recognizable keywords. More keywords can be added to `INDUSTRY_KEYWORDS` over time.
- **Detail page scraping is best-effort**: description, years, and employee extraction use multiple CSS selector fallbacks but may miss data on some listings. Missing fields score 0 points rather than penalizing. Run with `--debug` to inspect HTML if scores seem too low.
- **Existing sheet rows don't have new columns**: rows written before this change have 8 columns; new rows have 11 (added Revenue, Score, Rank). Old headers won't auto-update — manually add the 3 new column headers, or clear the sheet to let it recreate.
- **Cron requires Mac awake**: missed runs when the Mac is asleep. macOS Full Disk Access must be granted to `/usr/sbin/cron`.
- **Python 3.9 deprecation warnings**: google-auth warns about Python 3.9 EOL. Functional but noisy.

## Environment notes

- macOS (Apple Silicon) with Python 3.9.6 (system)
- Google Cloud project with service account credentials on disk (see `.env`)
- Google Sheet ID in `.env` (`GOOGLE_SHEET_ID`)
