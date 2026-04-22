# Decisions

## BusinessBroker.net over BizBuySell

BizBuySell uses Akamai Bot Manager which blocks all automated access — requests, cloudscraper, curl_cffi, Playwright headless, Playwright headed, even Google Sheets IMPORTHTML. BusinessBroker.net has significant listing overlap (brokers list on multiple platforms) and no bot protection. The trade-off is that some BizBuySell-exclusive listings won't be captured.

## curl_cffi over requests/Playwright

`curl_cffi` impersonates Chrome's TLS fingerprint, which is enough for BusinessBroker.net (no JS challenge). Much lighter than Playwright (no browser binary), and works on all architectures including Apple Silicon. Falls back gracefully on HTTP errors.

## Search results cards for most data, detail pages only for industry

BusinessBroker.net search result cards contain name, asking price, cash flow, and location — enough to filter. Only the industry/category field requires visiting the detail page. The script only visits detail pages for new listings that pass the SDE filter, minimizing requests.

## SDE filtering logic

- SDE >= $300k → included
- SDE < $300k → skipped entirely
- No SDE/cash flow listed → included with "NO SDE LISTED" flag (user wants to review these manually)

Intentionally permissive on missing data — better to surface a listing without SDE than miss a good one.

## Single-file architecture

Everything is in `monitor.py`. Appropriate for a personal monitoring script that runs on cron — simplicity over organization.

## seen_listings.json tracks URLs, not listing IDs

URLs are used as the dedup key rather than extracted listing IDs. Simpler and works even if the listing ID format changes. The `state_has_results` dict tracks whether each state has ever returned results, enabling the "zero results = something broke" warning.

## Google Sheets as the notification layer

No email/Slack/push notifications — the Google Sheet IS the notification surface. Warning rows (zero results detected) are also written to the sheet so they're visible in the same place.

## Service account auth (not OAuth)

Uses a Google Cloud service account with a JSON key file for Sheets access. No browser-based OAuth flow needed — works headlessly on cron. Sheet must be shared with the service account email.
