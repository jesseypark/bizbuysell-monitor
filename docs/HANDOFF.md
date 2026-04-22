# Handoff — Current State

## What's complete

- **Scraping**: working. Uses BusinessBroker.net via curl_cffi. Extracts listings from search results cards, visits detail pages for industry. Tested and producing results.
- **Google Sheets integration**: working. Service account auth connects, headers written, rows appended.
- **Filtering logic**: working. `parse_dollar_amount()`, `evaluate_listing()` unit-tested and passing.
- **Seen-listings tracking**: working. JSON file persists across runs, deduplicates correctly.
- **Zero-results warning**: implemented. Writes warning row to sheet if a state that previously had results returns zero.
- **Logging**: working. Dual output to console + `monitor.log` file.
- **Cron setup**: `run_monitor.sh` wrapper script ready. Cron line documented but not yet installed by user.
- **Project scaffolding**: `.env`, `.gitignore`, `requirements.txt`, `README.md` all current.

## What's not yet done

- **Cron not installed**: user needs to run `crontab -e` and add the cron line.
- **_scraper tab in Google Sheet**: leftover test tab from IMPORTHTML attempt. Contains #REF! errors. Should be deleted manually.
- **Cleanup venv**: extra packages from debugging (cloudscraper, playwright, undetected-chromedriver, nodriver, googlesearch-python, selenium) are installed but not needed. `pip install -r requirements.txt` in a fresh venv would be cleaner.

## Known limitations

- **Not BizBuySell**: uses BusinessBroker.net instead. Some BizBuySell-exclusive listings won't appear.
- **Industry requires detail page visit**: adds 1-3s per new matching listing. First run is slow (~780+ listings to scan, detail pages for matching ones). Subsequent runs are fast.
- **Python 3.9 deprecation warnings**: google-auth warns about Python 3.9 EOL. Functional but noisy.

## Environment notes

- macOS (Apple Silicon) with Python 3.9.6 (system)
- Google Cloud project with service account credentials on disk (see `.env`)
- Google Sheet ID in `.env` (`GOOGLE_SHEET_ID`)
