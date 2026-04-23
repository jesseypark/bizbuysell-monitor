#!/usr/bin/env python3
"""
Business Listing Monitor
Scrapes BusinessBroker.net for new business listings in target states,
filters by SDE/cash flow, and appends matches to a Google Sheet.

Uses BusinessBroker.net because BizBuySell blocks all automated access
via Akamai Bot Manager. BusinessBroker.net has significant listing overlap
and no bot protection.
"""

import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
SEEN_FILE = SCRIPT_DIR / "seen_listings.json"
LOG_FILE = SCRIPT_DIR / "monitor.log"
DEBUG_DIR = SCRIPT_DIR / "debug_html"

STATES = {
    "colorado": "CO",
    "washington": "WA",
}
BASE_URL = "https://www.businessbroker.net/state/{state}-businesses-for-sale.aspx"
MIN_SDE = 300_000
MAX_PAGES_PER_STATE = 50
REQUEST_DELAY = (2, 5)

GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE", str(SCRIPT_DIR / "credentials.json")
)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

DEBUG_MODE = "--debug" in sys.argv

logger = logging.getLogger("listing_monitor")


def setup_logging():
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(LOG_FILE)
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)


# --- HTTP client ---


def create_session():
    return requests


def fetch_page(session, url, retries=2):
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, impersonate="chrome", timeout=20)

            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                if attempt < retries:
                    logger.warning(
                        f"HTTP {resp.status_code} for {url}, retry {attempt + 1}/{retries}"
                    )
                    time.sleep(random.uniform(3, 7))
                    continue
                logger.error(f"HTTP {resp.status_code} for {url} after all retries")
                return None

            html = resp.text
            if DEBUG_MODE:
                save_debug_html(url, html)
            return html

        except Exception as e:
            if attempt < retries:
                logger.warning(f"Error fetching {url}: {e}, retry {attempt + 1}")
                time.sleep(random.uniform(3, 7))
            else:
                logger.error(f"Failed to fetch {url}: {e}")
                return None
    return None


def save_debug_html(url, html):
    DEBUG_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url)[:100]
    path = DEBUG_DIR / f"{slug}.html"
    path.write_text(html)
    logger.debug(f"Saved debug HTML: {path}")


# --- Seen listings tracking ---


def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            data = json.load(f)
            data["urls"] = set(data.get("urls", []))
            return data
    return {"urls": set(), "state_has_results": {}}


def save_seen(seen):
    data = {
        "urls": sorted(seen["urls"]),
        "state_has_results": seen.get("state_has_results", {}),
    }
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- Parsing helpers ---


def parse_dollar_amount(text):
    if not text:
        return None
    cleaned = text.strip().replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.lower() in (
        "n/a",
        "not disclosed",
        "call",
        "upon request",
    ):
        return None
    try:
        low = cleaned.lower()
        if low.endswith("m"):
            return int(float(low[:-1]) * 1_000_000)
        if low.endswith("k"):
            return int(float(low[:-1]) * 1_000)
        return int(float(cleaned))
    except (ValueError, IndexError):
        return None


# --- Search results page parsing ---


def extract_listings_from_search(html, state_abbr):
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for card in soup.find_all("div", class_="result-item"):
        listing = _parse_card(card, state_abbr)
        if listing:
            listings.append(listing)

    return listings


def _parse_card(card, state_abbr):
    link = card.find("a", href=lambda h: h and "/business-for-sale/" in h)
    if not link:
        return None

    href = link.get("href", "")
    if not href.startswith("http"):
        href = "https://www.businessbroker.net" + href

    h3 = card.find("h3")
    name = h3.get_text(strip=True) if h3 else "N/A"

    # Location — first div.location has "City, ST"
    loc_divs = card.find_all("div", class_="location")
    city = "N/A"
    state = state_abbr
    if loc_divs:
        loc_text = loc_divs[0].get_text(strip=True)
        parts = [p.strip() for p in loc_text.split(",")]
        if len(parts) >= 2:
            city = parts[0]
            state = parts[1].strip()

    # Asking price — from the span inside result-img
    asking_price = None
    img_div = card.find("div", class_="result-img")
    if img_div:
        price_span = img_div.find("span")
        if price_span:
            price_text = price_span.get_text(strip=True)
            asking_price = price_text.replace("Asking Price:", "").strip()

    # Cash flow — from listing-financials
    cash_flow = None
    fin_div = card.find("div", class_="listing-financials")
    if fin_div:
        for fin_item in fin_div.find_all("div", class_="financials"):
            label_span = fin_item.find("span")
            if label_span and "cash flow" in label_span.get_text(strip=True).lower():
                full_text = fin_item.get_text(strip=True)
                cash_flow = full_text.replace(label_span.get_text(strip=True), "").strip()
                break

    return {
        "name": name,
        "asking_price": asking_price,
        "cash_flow": cash_flow,
        "url": href,
        "city": city,
        "state": state,
        "industry": None,
    }


def get_max_page(html):
    soup = BeautifulSoup(html, "html.parser")
    pager = soup.find("ul", class_="searchPaging")
    if not pager:
        return 1
    pages = []
    for a in pager.find_all("a"):
        text = a.get_text(strip=True)
        if text.isdigit():
            pages.append(int(text))
    return max(pages) if pages else 1


# --- Industry classification ---

INDUSTRY_FILE = SCRIPT_DIR / "industries.json"

INDUSTRY_KEYWORDS = {
    "Plumbing": ["plumbing", "plumber", "drain", "sewer", "septic", "pipe"],
    "HVAC": ["hvac", "heating", "cooling", "air conditioning", "furnace"],
    "Electrical": ["electrical", "electrician", "wiring"],
    "Roofing": ["roofing", "roofer", "roof"],
    "Landscaping": ["landscaping", "lawn", "irrigation", "tree service", "tree care", "arborist"],
    "Construction": ["construction", "building", "contractor", "excavation", "demolition", "concrete", "paving", "asphalt"],
    "Painting": ["painting", "painter", "coatings"],
    "Pest Control": ["pest control", "exterminator", "termite"],
    "Cleaning Services": ["cleaning", "janitorial", "maid", "carpet cleaning", "pressure washing"],
    "Auto Repair": ["auto repair", "mechanic", "automotive", "auto body", "collision", "tire"],
    "Auto Dealership": ["auto dealer", "car dealer", "dealership", "used car"],
    "Restaurant": ["restaurant", "dining", "eatery", "bistro", "cafe", "diner", "pizza", "burger", "taco", "sushi", "bbq", "barbecue", "steakhouse", "grill"],
    "Fast Food / QSR": ["fast food", "franchise food", "drive-thru", "drive through"],
    "Bar / Brewery": ["bar", "brewery", "brewpub", "pub", "tavern", "taproom", "winery", "distillery"],
    "Coffee Shop": ["coffee", "espresso"],
    "Bakery": ["bakery", "donut", "doughnut", "pastry"],
    "Catering": ["catering", "caterer"],
    "Food Manufacturing": ["food manufacturing", "food production", "food processing", "meat processing", "bottling"],
    "Gas Station / C-Store": ["gas station", "fuel", "convenience store", "c-store"],
    "Retail": ["retail", "store", "shop", "boutique", "gift shop"],
    "E-Commerce": ["e-commerce", "ecommerce", "online store", "amazon", "shopify"],
    "Grocery": ["grocery", "supermarket", "market"],
    "Franchise": ["franchise"],
    "Hotel / Motel": ["hotel", "motel", "inn", "lodge", "resort", "hospitality"],
    "Fitness / Gym": ["fitness", "gym", "crossfit", "yoga", "pilates", "martial arts"],
    "Salon / Spa": ["salon", "spa", "barber", "hair", "beauty", "nail"],
    "Daycare / Childcare": ["daycare", "childcare", "child care", "preschool", "montessori"],
    "Senior Care": ["senior care", "assisted living", "elder care", "home health", "home care"],
    "Medical Practice": ["medical", "dental", "dentist", "physician", "clinic", "chiropractic", "optometry", "veterinary", "vet clinic", "orthodontic", "dermatology", "urgent care"],
    "Pharmacy": ["pharmacy", "pharmacist", "compounding"],
    "Staffing": ["staffing", "recruiting", "employment agency", "temp agency"],
    "IT / Technology": ["it services", "software", "saas", "technology", "tech", "cyber", "data center", "managed services", "msp", "web development", "app development"],
    "Marketing / Advertising": ["marketing", "advertising", "digital marketing", "seo", "media", "pr agency", "branding"],
    "Accounting / Finance": ["accounting", "bookkeeping", "tax", "cpa", "financial", "wealth management", "insurance agency"],
    "Legal": ["law firm", "legal", "attorney"],
    "Real Estate": ["real estate", "property management", "brokerage"],
    "Manufacturing": ["manufacturing", "fabrication", "machining", "machine shop", "welding", "cnc", "metal"],
    "Distribution / Wholesale": ["distribution", "wholesale", "distributor", "supply chain"],
    "Logistics / Trucking": ["logistics", "trucking", "freight", "shipping", "courier", "delivery", "moving company", "storage"],
    "Agriculture": ["farm", "ranch", "agriculture", "nursery", "greenhouse"],
    "Printing": ["printing", "print shop", "signage", "sign company"],
    "Pet Services": ["pet", "dog", "grooming", "kennel", "pet store", "veterinary"],
    "Education / Tutoring": ["tutoring", "education", "training", "school", "academy"],
    "Entertainment": ["entertainment", "amusement", "arcade", "bowling", "event", "party rental"],
    "Travel / Tourism": ["travel", "tour", "tourism"],
    "Waste Management": ["waste", "recycling", "junk removal", "dumpster", "trash", "disposal"],
}


def load_industries():
    if INDUSTRY_FILE.exists():
        with open(INDUSTRY_FILE) as f:
            return json.load(f)
    return {}


def save_industries(mapping):
    with open(INDUSTRY_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def classify_industry(business_name, industry_cache):
    name_lower = business_name.lower()

    if name_lower in industry_cache:
        return industry_cache[name_lower]

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                industry_cache[name_lower] = industry
                return industry

    industry_cache[name_lower] = "Other"
    return "Other"


# --- SDE filtering ---


def evaluate_listing(listing):
    cf = listing.get("cash_flow")
    amount = parse_dollar_amount(cf)

    if amount is not None:
        return amount >= MIN_SDE
    asking = parse_dollar_amount(listing.get("asking_price"))
    if asking is not None and asking >= 1_000_000:
        return True
    return False


# --- Google Sheets ---


def setup_sheets():
    if not GOOGLE_SHEET_ID:
        logger.warning("GOOGLE_SHEET_ID not set, skipping Sheets")
        return None
    if not Path(GOOGLE_CREDENTIALS_FILE).exists():
        logger.warning(f"Credentials file not found: {GOOGLE_CREDENTIALS_FILE}")
        return None

    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1

    if not sheet.row_values(1):
        sheet.append_row(
            [
                "Date Found",
                "State",
                "City",
                "Business Name",
                "Asking Price",
                "SDE",
                "URL",
                "Industry",
            ],
            value_input_option="USER_ENTERED",
        )

    return sheet


def append_to_sheet(sheet, listings):
    rows = []
    for lst in listings:
        rows.append(
            [
                lst["date_found"],
                lst["state"],
                lst["city"],
                lst["name"],
                lst.get("asking_price") or "N/A",
                lst.get("cash_flow") or "N/A",
                lst["url"],
                lst.get("industry", "Other"),
            ]
        )
    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info(f"Appended {len(rows)} rows to Google Sheet")


def append_warning_to_sheet(sheet, state_abbr):
    sheet.append_row(
        [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            state_abbr,
            "",
            f"⚠️ WARNING: No listings found for {state_abbr} — site may have changed, check script",
            "",
            "",
            "",
            "",
        ],
        value_input_option="USER_ENTERED",
    )


# --- Main ---


def main():
    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting listing monitor run")

    seen = load_seen()
    industry_cache = load_industries()
    all_new = []
    total_checked = 0

    sheet = None
    try:
        sheet = setup_sheets()
    except Exception as e:
        logger.error(f"Google Sheets setup failed: {e}")

    session = create_session()

    try:
        for state_slug, state_abbr in STATES.items():
            logger.info(f"--- Scraping {state_abbr} ---")
            had_results = seen.get("state_has_results", {}).get(state_slug, False)
            new_for_state = []
            listings_found_this_state = 0

            # Fetch page 1 to determine total pages
            page1_url = BASE_URL.format(state=state_slug)
            html = fetch_page(session, page1_url)
            if html is None:
                logger.error(f"Failed to fetch first page for {state_abbr}")
                if had_results and sheet:
                    try:
                        append_warning_to_sheet(sheet, state_abbr)
                    except Exception as e:
                        logger.error(f"Sheet warning failed: {e}")
                continue

            max_page = min(get_max_page(html), MAX_PAGES_PER_STATE)
            logger.info(f"  {max_page} pages to scan")

            for pg in range(1, max_page + 1):
                if pg > 1:
                    time.sleep(random.uniform(*REQUEST_DELAY))
                    page_url = f"{page1_url}?page={pg}"
                    html = fetch_page(session, page_url)
                    if html is None:
                        logger.error(f"  Failed to fetch page {pg}")
                        break

                listings = extract_listings_from_search(html, state_abbr)
                listings_found_this_state += len(listings)
                total_checked += len(listings)

                if not listings:
                    logger.info(f"  No listings on page {pg}, done with {state_abbr}")
                    break

                logger.info(f"  Page {pg}: {len(listings)} listings")

                for listing in listings:
                    if listing["url"] in seen["urls"]:
                        continue

                    if not evaluate_listing(listing):
                        logger.info(
                            f"  - Skipped (SDE < ${MIN_SDE:,}): {listing['name'][:50]}"
                        )
                        seen["urls"].add(listing["url"])
                        continue

                    listing["industry"] = classify_industry(listing["name"], industry_cache)
                    listing["date_found"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_for_state.append(listing)
                    seen["urls"].add(listing["url"])

                    logger.info(
                        f"  + {listing['name'][:50]} | "
                        f"Price: {listing['asking_price']} | "
                        f"CF: {listing['cash_flow']} | "
                        f"Industry: {listing['industry']}"
                    )

                save_seen(seen)

            # Zero-results warning
            if had_results and listings_found_this_state == 0:
                msg = f"No listings found for {state_abbr} — site may have changed"
                logger.warning(f"⚠️ {msg}")
                if sheet:
                    try:
                        append_warning_to_sheet(sheet, state_abbr)
                    except Exception as e:
                        logger.error(f"Sheet warning failed: {e}")

            if listings_found_this_state > 0:
                seen.setdefault("state_has_results", {})[state_slug] = True

            all_new.extend(new_for_state)

            # Delay between states
            time.sleep(random.uniform(3, 7))

    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)

    if sheet and all_new:
        try:
            append_to_sheet(sheet, all_new)
        except Exception as e:
            logger.error(f"Failed to write to sheet: {e}")

    save_seen(seen)
    save_industries(industry_cache)
    logger.info(
        f"Run complete: {total_checked} checked, {len(all_new)} new matches"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
