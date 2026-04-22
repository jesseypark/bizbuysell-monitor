# Business Listing Monitor

Monitors BusinessBroker.net for new business-for-sale listings in Colorado and Washington, filters by SDE/cash flow ($300k+), and appends matches to a Google Sheet.

## Why BusinessBroker.net instead of BizBuySell?

BizBuySell uses Akamai Bot Manager which blocks all automated access (requests, Playwright, Selenium — everything). BusinessBroker.net has significant listing overlap with BizBuySell (brokers list on multiple platforms) and no bot protection.

## Setup

### 1. Python environment

```bash
cd bizbuysell-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Sheets API & service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create one)
3. Enable the **Google Sheets API**:
   - Navigate to **APIs & Services > Library**
   - Search for "Google Sheets API" and click **Enable**
4. Enable the **Google Drive API** (same process — needed for sheet access)
5. Create a service account:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > Service Account**
   - Give it a name (e.g. `bizbuysell-monitor`) and click through
6. Create a key for the service account:
   - Click on the service account you just created
   - Go to the **Keys** tab
   - Click **Add Key > Create new key > JSON**
   - Save the downloaded file as `credentials.json` in this project directory
7. Create a Google Sheet and copy its ID from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`
8. Share the sheet with your service account:
   - Open the sheet, click **Share**
   - Paste the service account email (looks like `name@project.iam.gserviceaccount.com` — find it in the JSON file under `client_email`)
   - Give it **Editor** access

### 3. Environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `GOOGLE_CREDENTIALS_FILE` — path to your credentials JSON (default: `credentials.json`)
- `GOOGLE_SHEET_ID` — the sheet ID from step 7 above

### 4. Test run

```bash
source venv/bin/activate
python monitor.py
```

Add `--debug` to save raw HTML to `debug_html/` for troubleshooting:

```bash
python monitor.py --debug
```

### 5. Cron job (every hour, 8am-6pm Mountain)

```bash
crontab -e
```

Add this line (adjust the path to match your setup):

```
0 8-18 * * * /path/to/bizbuysell-monitor/run_monitor.sh
```

This assumes your Mac is set to Mountain time. To verify:

```bash
date +%Z  # Should show MDT or MST
```

If your Mac uses a different timezone, adjust the hours accordingly (e.g., for Pacific time use `7-17`).

## How it works

1. Fetches search results pages from BusinessBroker.net using `curl_cffi` (no browser needed)
2. Extracts listing data directly from search results cards: name, asking price, cash flow, location
3. Filters by SDE/cash flow:
   - **SDE >= $300k** — included
   - **SDE < $300k** — skipped
   - **No SDE listed** — included with "NO SDE LISTED" flag
4. For new matching listings, visits the detail page to get industry/category
5. Appends new matches to the Google Sheet
6. Tracks seen listings in `seen_listings.json` so duplicates are skipped on future runs
7. If a state that previously had results returns zero listings, appends a warning row to the sheet

## Files

| File | Purpose |
|---|---|
| `monitor.py` | Main script |
| `run_monitor.sh` | Cron wrapper (activates venv, runs script) |
| `seen_listings.json` | Tracks previously seen listing URLs (auto-created) |
| `monitor.log` | Run logs with timestamps |
| `.env` | Credentials path and sheet ID |
| `credentials.json` | Google service account key (not committed) |

## Sheet columns

| Date Found | State | City | Business Name | Asking Price | SDE | SDE Flag | URL | Industry |
|---|---|---|---|---|---|---|---|---|

## Troubleshooting

- **No listings found**: Run with `--debug` to save HTML to `debug_html/`. Check if BusinessBroker.net's page structure has changed.
- **Google Sheets errors**: Verify the service account email has Editor access on the sheet, and that both Sheets and Drive APIs are enabled.
- **Slow first run**: The initial run scans all pages and visits detail pages for every matching listing. Subsequent runs are fast since they only process new listings.
