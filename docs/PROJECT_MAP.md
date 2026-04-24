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
    │   ├── _parse_card()                  → extracts name/price/CF/revenue/location from one card
    │   ├── get_max_page()                 → reads pagination to find last page
    │   └── fetch_listing_details()        → scrapes detail page for description/years/employees
    │
    ├── Industry classification
    │   ├── classify_industry()    → keyword-based classification from business name
    │   ├── INDUSTRY_KEYWORDS      → canonical industry → keyword list mapping
    │   ├── load_industries() / save_industries() → persistent cache
    │   └── industries.json        → cached name→industry mappings (auto-created)
    │
    ├── Hard filters (pass/fail)
    │   ├── check_hard_filters()   → industry exclusion, min CF, max price, missing financials
    │   ├── REJECTED_INDUSTRIES    → auto-reject set (restaurants, trades, licensed professions)
    │   └── parse_dollar_amount()  → normalizes "$500K" / "$1.5M" / "$300,000" → int
    │
    ├── Scoring layer (0-100 scale)
    │   ├── score_listing()              → 3-tier scoring: economics + quality + keywords
    │   ├── compute_annual_debt_service() → SBA loan payment calc for DSCR
    │   └── rank_label()                 → maps score to A/B/C/D bucket
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
| `industries.json` | Cached business name → industry mappings (auto-created) |
| `monitor.log` | Append-only log with timestamps, counts, errors |
| `ontimeapp-*.json` | Google Cloud service account credentials (gitignored) |

## Data flow

1. curl_cffi fetches BusinessBroker.net search results (Chrome TLS fingerprint)
2. For each state (CO, WA): paginate through all search results pages
3. Parse listing cards from search results HTML (name, price, cash flow, revenue, location, URL)
4. Compare URLs against `seen_listings.json` → skip already-seen
5. Classify industry from business name using keyword matching
6. Hard filter: reject excluded industries, CF < $300k, price > $5M, missing financials
7. For passing listings: fetch detail page for description, years established, employee count
8. Score listing 0-100 (deal economics + business quality + description keywords)
9. Assign rank: A (70+), B (50-69), C (30-49), D (0-29)
10. Append matching listings as rows to Google Sheet (with Score + Rank columns)
11. If a state returns zero listings (and previously had results) → append warning row
12. Save updated seen URLs to JSON

## Scraping selectors (BusinessBroker.net HTML)

Search results page:
- Listing card: `div.result-item`
- Detail link: `a[href*="/business-for-sale/"]`
- Name: `h3` inside card
- Asking price: `span` inside `div.result-img`
- Cash flow: `div.financials` with `span` containing "Cash Flow"
- Revenue: `div.financials` with `span` containing "Revenue"
- Location: `div.location` (first one = "City, ST")
- Pagination: `ul.searchPaging` → `a` tags with page numbers
- URL pattern: `?page=N`

Detail page (fetched only for listings that pass hard filters):
- Description: `div.listing-description` or `div#TextDescription`
- Revenue, years, employees: parsed from structured detail fields via regex

## Scheduling

Cron: `0 8-18 * * 1-5` → hourly 8am-6pm Mountain time, weekdays only
