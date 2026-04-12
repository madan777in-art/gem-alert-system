"""
scraper.py — GeM Tender Scraper (API-based, Railway-compatible)

GeM portals block direct scraping from cloud IPs.
This version uses:
1. GeM's own public REST API endpoints
2. Public tender aggregator APIs (no login needed)
3. RSS/XML feeds where available
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import random
import re
import json
from typing import List, Dict, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

RETRY_LIMIT = 3
RETRY_DELAY = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

# ── Keywords to search ────────────────────────────────────────────────────────
SEARCH_KEYWORDS = [
    "e-learning",
    "elearning",
    "content development",
    "content design",
    "storyboarding",
    "interactive content",
    "iGOT",
    "augmented reality",
    "virtual reality",
    "immersive learning",
    "AR VR",
]


def get_headers(json_mode: bool = False) -> Dict:
    base = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    if json_mode:
        base["Accept"] = "application/json, text/plain, */*"
        base["Content-Type"] = "application/json"
    else:
        base["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return base


def safe_get(url: str, json_mode: bool = False, timeout: int = 20) -> Optional[requests.Response]:
    """HTTP GET with retry. Returns Response or None."""
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            time.sleep(random.uniform(1, 3))
            resp = requests.get(url, headers=get_headers(json_mode), timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt} failed for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
    logger.error(f"All attempts failed: {url}")
    return None


def extract_bid_no(text: str) -> Optional[str]:
    match = re.search(r"GEM[/\-]\d{4}[/\-][A-Z][/\-]\d+", text, re.IGNORECASE)
    return match.group(0).upper().replace("-", "/") if match else None


def extract_dates(text: str):
    dates = re.findall(r"\d{2}[-/]\d{2}[-/]\d{4}", text)
    return (dates[0] if dates else "N/A"), (dates[1] if len(dates) > 1 else "N/A")


def extract_value(text: str) -> str:
    match = re.search(
        r"(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?(?:\s?(?:Lakh|L|Cr|Crore))?",
        text, re.IGNORECASE
    )
    return match.group(0).strip() if match else "Not specified"


def make_tender_dict(bid_no, title, org, desc, value, start, end, url, source) -> Dict:
    return {
        "bid_no": bid_no,
        "title": str(title)[:200],
        "organisation": str(org)[:200],
        "description": str(desc)[:600],
        "value": value,
        "start_date": start,
        "end_date": end,
        "url": url,
        "source": source,
    }


# ── SOURCE 1: GeM Public Search API ──────────────────────────────────────────
def scrape_gem_api() -> List[Dict]:
    """
    GeM has a public search API used by their own website.
    This is more reliable than HTML scraping.
    """
    tenders = []
    logger.info("Trying GeM public search API ...")

    # GeM's internal search API endpoints
    api_urls = [
        "https://gem.gov.in/api/v1/search/bids?keyword={kw}&page=1&size=20",
        "https://gem.gov.in/api/search?q={kw}&type=bid&page=1",
        "https://bidplus.gem.gov.in/api/bids/search?keyword={kw}",
    ]

    for kw in SEARCH_KEYWORDS:
        for api_template in api_urls:
            url = api_template.format(kw=quote(kw))
            try:
                resp = safe_get(url, json_mode=True)
                if not resp:
                    continue

                # Try parsing as JSON
                try:
                    data = resp.json()
                    extracted = parse_gem_api_json(data, kw)
                    if extracted:
                        tenders.extend(extracted)
                        logger.info(f"  GeM API [{kw}]: {len(extracted)} results")
                        break  # Found results from this API, move to next keyword
                except json.JSONDecodeError:
                    # Not JSON — try HTML parsing
                    soup = BeautifulSoup(resp.text, "html.parser")
                    extracted = parse_gem_html(soup, kw)
                    if extracted:
                        tenders.extend(extracted)
                        logger.info(f"  GeM HTML [{kw}]: {len(extracted)} results")
                        break

            except Exception as e:
                logger.debug(f"GeM API attempt failed for {kw}: {e}")
                continue

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"GeM API total unique: {len(unique)}")
    return unique


def parse_gem_api_json(data, keyword: str) -> List[Dict]:
    """Parse various JSON response formats from GeM API."""
    tenders = []
    items = []

    # Try different JSON structures
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ["data", "results", "bids", "tenders", "items", "content"]:
            if key in data:
                items = data[key] if isinstance(data[key], list) else [data[key]]
                break

    for item in items:
        if not isinstance(item, dict):
            continue
        text = json.dumps(item)
        bid_no = (
            item.get("bidNumber") or item.get("bid_number") or
            item.get("bidNo") or item.get("id") or
            extract_bid_no(text)
        )
        if not bid_no:
            continue

        title = (
            item.get("bidName") or item.get("title") or
            item.get("name") or item.get("description", "")[:100]
        )
        org = (
            item.get("buyerOrganisation") or item.get("organisation") or
            item.get("department") or item.get("ministry") or "Government Department"
        )
        desc = (
            item.get("description") or item.get("scopeOfWork") or
            item.get("summary") or text[:500]
        )
        value = item.get("estimatedValue") or item.get("value") or extract_value(text)
        start = item.get("bidStartDate") or item.get("startDate") or "N/A"
        end = item.get("bidEndDate") or item.get("endDate") or item.get("closingDate") or "N/A"
        url = (
            item.get("url") or item.get("link") or
            f"https://bidplus.gem.gov.in/all-bids"
        )

        tenders.append(make_tender_dict(
            str(bid_no), str(title), str(org), str(desc),
            str(value), str(start), str(end), str(url), "gem.gov.in API"
        ))

    return tenders


def parse_gem_html(soup: BeautifulSoup, keyword: str) -> List[Dict]:
    """Fallback HTML parser for GeM search results."""
    tenders = []
    blocks = soup.find_all(["div", "article", "li", "tr"])
    for block in blocks:
        text = block.get_text(separator=" ", strip=True)
        bid_no = extract_bid_no(text)
        if not bid_no or len(text) < 30:
            continue
        title_tag = block.find(["h2", "h3", "h4", "a", "strong"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]
        link_tag = block.find("a", href=True)
        url = link_tag["href"] if link_tag else "https://gem.gov.in"
        if url.startswith("/"):
            url = "https://gem.gov.in" + url
        start, end = extract_dates(text)
        tenders.append(make_tender_dict(
            bid_no, title, "Government of India", text[:500],
            extract_value(text), start, end, url, "gem.gov.in"
        ))
    return tenders


# ── SOURCE 2: Public Tender Aggregators (no login, free APIs) ─────────────────
def scrape_tender_aggregators() -> List[Dict]:
    """
    Scrape public tender aggregator websites that re-publish GeM data.
    These are accessible from cloud servers unlike direct GeM portals.
    """
    tenders = []
    logger.info("Scraping public tender aggregators ...")

    sources = [
        {
            "name": "nationaltenders.com",
            "urls": [
                f"https://www.nationaltenders.com/site/keyword/{quote(kw)}"
                for kw in ["e-learning+igot", "content+development+gem", "storyboarding+gem"]
            ]
        },
        {
            "name": "tendersontime.com",
            "urls": [
                "https://www.tendersontime.com/indiaproducts/indian-learning-and-development-tenders-3920/",
                "https://www.tendersontime.com/popular-tenders/multimedia-tenders/",
            ]
        },
        {
            "name": "tenderdetail.com",
            "urls": [
                "https://www.tenderdetail.com/e-procurement-tender-list/gem-tender",
            ]
        },
    ]

    for source in sources:
        for url in source["urls"]:
            try:
                resp = safe_get(url)
                if not resp:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                found = parse_aggregator_page(soup, source["name"], url)
                tenders.extend(found)
                logger.info(f"  {source['name']}: {len(found)} tenders from {url}")
            except Exception as e:
                logger.error(f"Aggregator error {source['name']}: {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"Aggregators total unique: {len(unique)}")
    return unique


def parse_aggregator_page(soup: BeautifulSoup, source_name: str, source_url: str) -> List[Dict]:
    tenders = []
    # Look for any element containing a GEM bid number
    all_blocks = soup.find_all(["div", "tr", "li", "article", "p", "td"])
    seen_bids = set()

    for block in all_blocks:
        text = block.get_text(separator=" ", strip=True)
        bid_no = extract_bid_no(text)

        if not bid_no or bid_no in seen_bids or len(text) < 20:
            continue
        seen_bids.add(bid_no)

        title_tag = block.find(["h2", "h3", "h4", "a", "strong", "b"])
        title = title_tag.get_text(strip=True) if title_tag else text[:150]

        link_tag = block.find("a", href=True)
        url = link_tag["href"] if link_tag else source_url
        if url.startswith("/"):
            domain = "/".join(source_url.split("/")[:3])
            url = domain + url

        org_match = re.search(
            r"(Ministry|Department|Institute|Council|Board|Authority|"
            r"AIIMS|IIT|NIC|University|Hospital|Academy|Office)[^\n,;]{0,80}",
            text, re.IGNORECASE
        )
        org = org_match.group(0).strip() if org_match else "Government Department"

        # Extract EMD as value fallback
        emd_match = re.search(r"EMD[:\s]+(?:Rs\.?|INR|₹)?\s*[\d,]+", text, re.IGNORECASE)
        value = emd_match.group(0) if emd_match else extract_value(text)

        start, end = extract_dates(text)

        tenders.append(make_tender_dict(
            bid_no, title, org, text[:600],
            value, start, end, url, source_name
        ))

    return tenders


# ── SOURCE 3: CPPP (Central Public Procurement Portal) — official GeM feed ────
def scrape_cppp() -> List[Dict]:
    """
    CPPP is the official government procurement portal that syncs with GeM.
    Much more accessible than direct GeM portals.
    """
    tenders = []
    logger.info("Scraping CPPP (Central Public Procurement Portal) ...")

    urls = [
        "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata",
        "https://eprocure.gov.in/cppp/tendersNews",
    ]

    search_terms = ["e-learning", "iGOT", "content development", "storyboarding"]

    for term in search_terms:
        url = f"https://eprocure.gov.in/cppp/viewtenders/search/{quote(term)}/cpppdata"
        try:
            resp = safe_get(url)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                text = row.get_text(separator=" ", strip=True)
                bid_no = extract_bid_no(text)
                if not bid_no:
                    continue
                cells = row.find_all("td")
                title = cells[0].get_text(strip=True) if cells else text[:120]
                org = cells[1].get_text(strip=True) if len(cells) > 1 else "Government"
                start, end = extract_dates(text)
                link = row.find("a", href=True)
                url_link = link["href"] if link else "https://eprocure.gov.in"
                tenders.append(make_tender_dict(
                    bid_no, title, org, text[:500],
                    "N/A", start, end, url_link, "eprocure.gov.in (CPPP)"
                ))
            logger.info(f"  CPPP [{term}]: found tenders")
        except Exception as e:
            logger.error(f"CPPP error for {term}: {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"CPPP total unique: {len(unique)}")
    return unique


# ── SOURCE 4: Fallback — search engine scraping for recent GeM bids ───────────
def scrape_search_fallback() -> List[Dict]:
    """
    Last resort: use DuckDuckGo HTML search to find recent GeM tenders.
    Works reliably from cloud servers.
    """
    tenders = []
    logger.info("Running search engine fallback ...")

    queries = [
        "site:bidplus.gem.gov.in e-learning content development iGOT 2026",
        "site:bidplus.gem.gov.in storyboarding augmented reality 2026",
        "GEM/2026 e-learning content development storyboarding iGOT bid",
    ]

    for query in queries:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            resp = safe_get(url)
            if not resp:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.find_all("div", class_=re.compile(r"result", re.I))

            for r in results:
                text = r.get_text(separator=" ", strip=True)
                bid_no = extract_bid_no(text)
                if not bid_no:
                    continue

                title_tag = r.find(["h2", "a"])
                title = title_tag.get_text(strip=True) if title_tag else text[:120]

                link_tag = r.find("a", href=True)
                url_link = link_tag["href"] if link_tag else "https://bidplus.gem.gov.in/all-bids"

                start, end = extract_dates(text)
                tenders.append(make_tender_dict(
                    bid_no, title, "GeM Portal",
                    text[:500], "N/A", start, end,
                    url_link, "bidplus.gem.gov.in"
                ))

            logger.info(f"  Search fallback [{query[:40]}...]: {len(results)} results")

        except Exception as e:
            logger.error(f"Search fallback error: {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"Search fallback unique: {len(unique)}")
    return unique


# ── Master scrape function ────────────────────────────────────────────────────
def scrape_all_portals() -> List[Dict]:
    all_tenders = []

    sources = [
        ("GeM Public API",          scrape_gem_api),
        ("Tender Aggregators",      scrape_tender_aggregators),
        ("CPPP eProcure",           scrape_cppp),
        ("Search Engine Fallback",  scrape_search_fallback),
    ]

    for name, fn in sources:
        try:
            logger.info(f"--- Starting: {name} ---")
            results = fn()
            all_tenders.extend(results)
            logger.info(f"--- Completed {name}: {len(results)} tenders ---")
        except Exception as e:
            logger.error(f"Source '{name}' completely failed: {e}")

    # Final global deduplication by bid_no
    seen = set()
    unique = []
    for t in all_tenders:
        if t["bid_no"] not in seen:
            seen.add(t["bid_no"])
            unique.append(t)

    logger.info(f"=== GRAND TOTAL unique tenders: {len(unique)} ===")
    return unique
