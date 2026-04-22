# Project Map

## What this does

Monitors BusinessBroker.net for new business listings in Colorado and Washington state. Filters by SDE/cash flow >= $300k, tracks seen listings to avoid duplicates, and appends new matches to a Google Sheet.

## Architecture

```
monitor.py          Main script — single-file, runs end-to-end
    │
    ├── HTTP layer (curl_cffi with Chrome TLS impersonation)
    │   ├── create_session()         → returns curl_cffi requests module
    │   └── fetch_page()             → GET with retries, handles 404/errors
    │
    ├── Scraping layer (BeautifulSoup)
    │   ├── extract_listings_from_search() → parses search results cards
    │   ├── _parse_card()                  → extracts name/price/CF/location from one card
    │   ├── get_max_page()                 → reads pagination to find last page
    │   └── extract_industry()             → parses detail page for industry
    │
    ├── Filtering layer
    │   ├── parse_dollar_amount() → normalizes "$500K" / "$1.5M" / "$300,000" → int
    │   └── evaluate_listing()    → include/skip/flag based on SDE threshold
    │
    ├── Persistence layer
    │   ├── load_seen() / save_seen() → JSON file tracking seen listing URLs
    │   └── seen_listings.json        → the data file (auto-created)
    │
    └── Output layer (Google Sheets via gspread)
        ├── setup_sheets()           → authenticates, ensures headers exist
        ├── append_to_sheet()        → batch-appends new listings
        └── append_warning_to_sheet() → writes warning row if zero results
```

## Key files

| File | Purpose |
|---|---|
| `monitor.py` | Everything — scraping, filtering, persistence, Sheets output |
| `run_monitor.sh` | Cron wrapper — cd's to project dir, activates venv, runs script |
| `requirements.txt` | Python deps: beautifulsoup4, curl_cffi, gspread, google-auth, dotenv |
| `.env` | Runtime config: credentials path + sheet ID |
| `seen_listings.json` | Tracks URLs already processed (auto-created at runtime) |
| `monitor.log` | Append-only log with timestamps, counts, errors |
| `ontimeapp-*.json` | Google Cloud service account credentials (gitignored) |

## Data flow

1. curl_cffi fetches BusinessBroker.net search results (Chrome TLS fingerprint)
2. For each state (CO, WA): paginate through all search results pages
3. Parse listing cards directly from search results HTML (name, price, cash flow, location, URL)
4. Compare URLs against `seen_listings.json` → skip already-seen
5. Filter: SDE >= $300k → include; SDE < $300k → skip; no SDE → flag "NO SDE LISTED"
6. For new matching listings only: visit detail page → extract industry via `div.industry`
7. Append matching listings as rows to Google Sheet
8. If a state returns zero listings (and previously had results) → append warning row
9. Save updated seen URLs to JSON

## Scraping selectors (BusinessBroker.net HTML)

Search results page:
- Listing card: `div.result-item`
- Detail link: `a[href*="/business-for-sale/"]`
- Name: `h3` inside card
- Asking price: `span` inside `div.result-img`
- Cash flow: `div.financials` with `span` containing "Cash Flow"
- Location: `div.location` (first one = "City, ST")
- Pagination: `ul.searchPaging` → `a` tags with page numbers
- URL pattern: `?page=N`

Detail page:
- Industry: `div.industry`
- Fallback: breadcrumbs second-to-last `li`

## Scheduling

Cron: `0 8-18 * * *` → hourly 8am-6pm Mountain time
