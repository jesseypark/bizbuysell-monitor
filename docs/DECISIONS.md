# Decisions

## BusinessBroker.net over BizBuySell

BizBuySell uses Akamai Bot Manager which blocks all automated access — requests, cloudscraper, curl_cffi, Playwright headless, Playwright headed, even Google Sheets IMPORTHTML. BusinessBroker.net has significant listing overlap (brokers list on multiple platforms) and no bot protection. The trade-off is that some BizBuySell-exclusive listings won't be captured.

## curl_cffi over requests/Playwright

`curl_cffi` impersonates Chrome's TLS fingerprint, which is enough for BusinessBroker.net (no JS challenge). Much lighter than Playwright (no browser binary), and works on all architectures including Apple Silicon. Falls back gracefully on HTTP errors.

## Detail pages only for scored listings

Search result cards provide name, asking price, cash flow, revenue, and location — enough for hard filters. Detail pages are fetched only for listings that pass all hard filters, to extract description text, years established, and employee count for the scoring system. This keeps the common case fast (most listings are filtered out before any detail fetch).

## Keyword-based industry classification

Industry is derived from the business name using a canonical keyword map (`INDUSTRY_KEYWORDS`) rather than scraping it from the listing detail page. A persistent `industries.json` cache ensures consistency across runs. Keywords are grouped to avoid duplicates (e.g., "sewer", "drain", "plumber" all map to "Plumbing"). Unmatched names get "Other".

## Hard filter logic (replaces old SDE-only filter)

Pass/fail gates applied before scoring:
1. Industry exclusion: auto-reject restaurants, trades (plumbing/electrical/roofing/HVAC), licensed professions (legal, medical, pharmacy)
2. Minimum cash flow: reject if stated CF < $300k
3. Asking price ceiling: reject if asking > $5M (SBA 7(a) cap)
4. Missing financials: reject if both revenue AND cash flow are missing (unless asking >= $1M)

## Scoring system (100-point scale)

Three-tier scoring for listings that pass hard filters:
- Tier 1 — Deal Economics (50 pts): SDE multiple, DSCR (SBA 10yr @ 10.5%), cash flow margin
- Tier 2 — Business Quality (30 pts): years established, revenue size, employee count
- Tier 3 — Description Keywords (20 pts): bonuses for recurring/absentee/growth, penalties for distress/franchise/declining

Rank buckets: A (70-100) = request CIM, B (50-69) = review manually, C (30-49) = backlog, D (0-29) = skip.

Missing data fields score 0 rather than penalizing — a listing with only search card data (no detail page info) can still reach ~50 pts on deal economics alone.

## Single-file architecture

Everything is in `monitor.py`. Appropriate for a personal monitoring script that runs on cron — simplicity over organization.

## seen_listings.json tracks URLs, not listing IDs

URLs are used as the dedup key rather than extracted listing IDs. Simpler and works even if the listing ID format changes. The `state_has_results` dict tracks whether each state has ever returned results, enabling the "zero results = something broke" warning.

## Google Sheets as the notification layer

No email/Slack/push notifications — the Google Sheet IS the notification surface. Warning rows (zero results detected) are also written to the sheet so they're visible in the same place.

## Service account auth (not OAuth)

Uses a Google Cloud service account with a JSON key file for Sheets access. No browser-based OAuth flow needed — works headlessly on cron. Sheet must be shared with the service account email.
