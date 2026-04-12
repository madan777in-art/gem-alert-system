"""
scraper.py — GeM Tender Scraper (Cloud-compatible, NO direct GeM access)

GeM blocks ALL cloud server IPs (Railway, Render, AWS, etc.)
This version scrapes only third-party aggregators that republish GeM data
and are fully accessible from cloud servers.

Sources used:
1. BidAssist (bidassist.com) — India's largest tender aggregator
2. TendersOnTime (tendersontime.com) — republishes all GeM bids
3. NationalTenders (nationaltenders.com) — GeM keyword search
4. DuckDuckGo HTML search — finds recent GeM bid numbers
5. TenderDetail (tenderdetail.com) — live GeM mirror
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import random
import re
from typing import List, Dict, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

RETRY_LIMIT = 3
RETRY_DELAY = 4

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

SEARCH_KEYWORDS = [
    "e-learning",
    "content development",
    "content design",
    "storyboarding",
    "interactive content",
    "iGOT",
    "augmented reality",
    "virtual reality",
    "immersive learning",
]


def get_headers() -> Dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


def safe_fetch(url: str, timeout: int = 25) -> Optional[str]:
    """Fetch URL with retry. Returns HTML text or None."""
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            time.sleep(random.uniform(2, 4))
            resp = requests.get(url, headers=get_headers(), timeout=timeout)
            resp.raise_for_status()
            if len(resp.text) < 200:
                logger.warning(f"Very short response from {url} — skipping")
                return None
            return resp.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt} failed for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
    logger.error(f"All {RETRY_LIMIT} attempts failed: {url}")
    return None


def extract_bid_no(text: str) -> Optional[str]:
    match = re.search(r"GEM[/\-]\d{4}[/\-][A-Z][/\-]\d+", text, re.IGNORECASE)
    return match.group(0).upper().replace("-", "/") if match else None


def extract_dates(text: str):
    dates = re.findall(r"\d{2}[-/]\d{2}[-/]\d{4}", text)
    return (dates[0] if dates else "N/A"), (dates[1] if len(dates) > 1 else "N/A")


def extract_value(text: str) -> str:
    match = re.search(
        r"(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?(?:\s?(?:Lakh|Lac|L|Cr|Crore))?",
        text, re.IGNORECASE
    )
    return match.group(0).strip() if match else "Not specified"


def extract_org(text: str) -> str:
    match = re.search(
        r"(Ministry|Department|Institute|Council|Board|Authority|Office|"
        r"AIIMS|IIT|NIC|DRDO|ISRO|University|Hospital|Academy|"
        r"Corporation|Commission|Bureau|Directorate)[^\n,;|]{0,80}",
        text, re.IGNORECASE
    )
    return match.group(0).strip() if match else "Government Department"


def build_tender(bid_no, title, org, desc, value, start, end, url, source) -> Dict:
    return {
        "bid_no": str(bid_no).strip(),
        "title": str(title).strip()[:200],
        "organisation": str(org).strip()[:200],
        "description": str(desc).strip()[:600],
        "value": str(value).strip(),
        "start_date": str(start).strip(),
        "end_date": str(end).strip(),
        "url": str(url).strip(),
        "source": source,
    }


def parse_blocks_for_tenders(soup: BeautifulSoup, source_name: str, base_url: str) -> List[Dict]:
    """
    Generic parser — finds any HTML block containing a GEM bid number.
    Works across different aggregator site layouts.
    """
    tenders = []
    seen_bids = set()

    # Cast a wide net — check all meaningful block elements
    blocks = soup.find_all(["div", "tr", "li", "article", "section", "td"])

    for block in blocks:
        text = block.get_text(separator=" ", strip=True)
        if len(text) < 15:
            continue

        bid_no = extract_bid_no(text)
        if not bid_no or bid_no in seen_bids:
            continue
        seen_bids.add(bid_no)

        # Title: prefer heading/link tags
        title_tag = block.find(["h1", "h2", "h3", "h4", "h5", "a", "strong", "b"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]
        if len(title) < 5:
            title = text[:120]

        # URL: prefer internal links
        link_tag = block.find("a", href=True)
        if link_tag:
            href = link_tag["href"]
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                domain = "/".join(base_url.split("/")[:3])
                url = domain + href
            else:
                url = base_url
        else:
            url = f"https://bidplus.gem.gov.in/all-bids"

        start, end = extract_dates(text)
        org = extract_org(text)
        value = extract_value(text)

        tenders.append(build_tender(
            bid_no, title, org, text[:600],
            value, start, end, url, source_name
        ))

    return tenders


# ── SOURCE 1: BidAssist ───────────────────────────────────────────────────────
def scrape_bidassist() -> List[Dict]:
    tenders = []
    logger.info("Scraping bidassist.com ...")

    urls = [
        "https://bidassist.com/all-tenders/gem-procurement-source/active",
        "https://bidassist.com/tenders?keyword=e-learning&source=gem",
        "https://bidassist.com/tenders?keyword=iGOT&source=gem",
        "https://bidassist.com/tenders?keyword=content+development&source=gem",
        "https://bidassist.com/tenders?keyword=storyboarding&source=gem",
    ]

    for url in urls:
        try:
            html = safe_fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_blocks_for_tenders(soup, "bidassist.com", url)
            tenders.extend(found)
            logger.info(f"  BidAssist {url[-40:]}: {len(found)} tenders")
        except Exception as e:
            logger.error(f"BidAssist error {url}: {e}")

    return tenders


# ── SOURCE 2: TendersOnTime ───────────────────────────────────────────────────
def scrape_tendersontime() -> List[Dict]:
    tenders = []
    logger.info("Scraping tendersontime.com ...")

    urls = [
        "https://www.tendersontime.com/indiaproducts/indian-learning-and-development-tenders-3920/",
        "https://www.tendersontime.com/popular-tenders/multimedia-tenders/",
        "https://www.tendersontime.com/searchrfp/global-e--learning-rfp-12174/",
        "https://www.tendersontime.com/indiaproducts/indian-augmented-reality-tenders-16100/",
    ]

    for url in urls:
        try:
            html = safe_fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_blocks_for_tenders(soup, "tendersontime.com", url)
            tenders.extend(found)
            logger.info(f"  TendersOnTime {url[-40:]}: {len(found)} tenders")
        except Exception as e:
            logger.error(f"TendersOnTime error {url}: {e}")

    return tenders


# ── SOURCE 3: NationalTenders ─────────────────────────────────────────────────
def scrape_nationaltenders() -> List[Dict]:
    tenders = []
    logger.info("Scraping nationaltenders.com ...")

    keywords = [
        "e-learning+content+development",
        "iGOT+storyboarding",
        "augmented+reality+gem",
        "virtual+reality+gem",
        "content+development+gem",
    ]

    for kw in keywords:
        url = f"https://www.nationaltenders.com/site/keyword/{kw}"
        try:
            html = safe_fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_blocks_for_tenders(soup, "nationaltenders.com", url)
            tenders.extend(found)
            logger.info(f"  NationalTenders [{kw}]: {len(found)} tenders")
        except Exception as e:
            logger.error(f"NationalTenders error {kw}: {e}")

    return tenders


# ── SOURCE 4: TenderDetail ────────────────────────────────────────────────────
def scrape_tenderdetail() -> List[Dict]:
    tenders = []
    logger.info("Scraping tenderdetail.com ...")

    urls = [
        "https://www.tenderdetail.com/e-procurement-tender-list/gem-tender",
        "https://www.tenderdetail.com/bids/multimedia-tenders.html",
    ]

    for url in urls:
        try:
            html = safe_fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_blocks_for_tenders(soup, "tenderdetail.com", url)
            tenders.extend(found)
            logger.info(f"  TenderDetail {url[-40:]}: {len(found)} tenders")
        except Exception as e:
            logger.error(f"TenderDetail error {url}: {e}")

    return tenders


# ── SOURCE 5: FirstTender ─────────────────────────────────────────────────────
def scrape_firsttender() -> List[Dict]:
    tenders = []
    logger.info("Scraping firsttender.com ...")

    urls = [
        "https://www.firsttender.com/bids/multimedia-tenders.html",
        "https://www.firsttender.com/bids/e-learning-tenders.html",
    ]

    for url in urls:
        try:
            html = safe_fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_blocks_for_tenders(soup, "firsttender.com", url)
            tenders.extend(found)
            logger.info(f"  FirstTender {url[-40:]}: {len(found)} tenders")
        except Exception as e:
            logger.error(f"FirstTender error {url}: {e}")

    return tenders


# ── SOURCE 6: DuckDuckGo search fallback ─────────────────────────────────────
def scrape_duckduckgo() -> List[Dict]:
    """
    Search DuckDuckGo for recent GeM bid numbers.
    DuckDuckGo HTML interface is always accessible from cloud servers.
    """
    tenders = []
    logger.info("Running DuckDuckGo search fallback ...")

    queries = [
        "GEM/2026 e-learning content development iGOT storyboarding bid",
        "GEM/2026 augmented reality virtual reality immersive learning bid",
        "site:bidalert.in GEM 2026 e-learning iGOT content development",
        "site:tendersplus.com GEM e-learning iGOT storyboarding 2026",
    ]

    for query in queries:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            html = safe_fetch(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            results = soup.find_all("div", class_=re.compile(r"result", re.I))

            for r in results:
                text = r.get_text(separator=" ", strip=True)
                bid_no = extract_bid_no(text)
                if not bid_no:
                    continue

                title_tag = r.find(["h2", "h3", "a"])
                title = title_tag.get_text(strip=True) if title_tag else text[:120]

                link_tag = r.find("a", href=True)
                link = link_tag["href"] if link_tag else "https://bidplus.gem.gov.in/all-bids"

                start, end = extract_dates(text)
                tenders.append(build_tender(
                    bid_no, title, extract_org(text), text[:500],
                    extract_value(text), start, end,
                    link, "bidplus.gem.gov.in"
                ))

            logger.info(f"  DuckDuckGo [{query[:45]}]: found {len(tenders)} so far")
            time.sleep(random.uniform(3, 6))  # Be polite to DDG

        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    return unique


# ── MASTER FUNCTION ───────────────────────────────────────────────────────────
def scrape_all_portals() -> List[Dict]:
    all_tenders = []

    sources = [
        ("BidAssist",         scrape_bidassist),
        ("TendersOnTime",     scrape_tendersontime),
        ("NationalTenders",   scrape_nationaltenders),
        ("TenderDetail",      scrape_tenderdetail),
        ("FirstTender",       scrape_firsttender),
        ("DuckDuckGo Search", scrape_duckduckgo),
    ]

    for name, fn in sources:
        try:
            logger.info(f"--- Starting source: {name} ---")
            results = fn()
            all_tenders.extend(results)
            logger.info(f"--- Completed {name}: {len(results)} tenders ---")
        except Exception as e:
            logger.error(f"Source '{name}' completely failed: {e}")
            # Continue with next source — never crash the whole cycle

    # Global deduplication by bid_no
    seen = set()
    unique = []
    for t in all_tenders:
        if t["bid_no"] not in seen:
            seen.add(t["bid_no"])
            unique.append(t)

    logger.info(f"=== GRAND TOTAL unique tenders scraped: {len(unique)} ===")
    return unique
