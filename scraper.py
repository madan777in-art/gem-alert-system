"""
scraper.py - GeM Tender Alert System v3
Sources that actually work on Railway:
  - BidAssist (public search pages)
  - Google News RSS (confirmed working)
  - CPPP (Central Public Procurement Portal - govt, works on cloud)
  - TendersOnTime
  - NationalTenders
  - Merx / procurement aggregators
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import urllib.parse
from typing import List, Dict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

KEYWORDS = [
    "e-learning", "eLearning", "LMS", "learning management",
    "iGOT", "content development", "content design", "storyboarding",
    "interactive content", "AR/VR", "augmented reality", "virtual reality",
    "immersive learning", "immersive solutions", "digital learning",
    "online training", "SCORM", "courseware",
]

KEYWORD_GROUPS = [
    "e-learning iGOT content development",
    "storyboarding augmented reality virtual reality",
    "LMS digital learning immersive",
    "content design interactive courseware SCORM",
    "government training platform e-learning",
]


def safe_get(url: str, timeout: int = 15) -> requests.Response | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if len(r.text) > 500:
                return r
            logger.warning(f"Too short response from {url}")
            return None
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed [{url}]: {e}")
            time.sleep(5 * (attempt + 1))
    logger.error(f"All attempts failed: {url}")
    return None


def keyword_match(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)


# ── SOURCE 1: Google News RSS (confirmed working) ─────────────────────────────
def scrape_google_news_rss() -> List[Dict]:
    results = []
    queries = [
        "GeM tender e-learning iGOT content development",
        "GeM bid storyboarding augmented reality immersive",
        "government e-marketplace digital learning LMS",
        "GeM 2026 AR VR training content",
    ]
    for q in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        logger.info(f"  Google News RSS [{q[:40]}]: {len(items)} items checked")
        for item in items:
            title = item.find("title").get_text(strip=True) if item.find("title") else ""
            link = item.find("link").get_text(strip=True) if item.find("link") else ""
            desc = item.find("description").get_text(strip=True) if item.find("description") else ""
            pub = item.find("pubDate").get_text(strip=True) if item.find("pubDate") else ""
            combined = f"{title} {desc}"
            if keyword_match(combined):
                results.append({
                    "title": title,
                    "url": link,
                    "source": "Google News RSS",
                    "published": pub,
                    "bid_no": "",
                    "org": "",
                    "value": "",
                })
        time.sleep(2)
    logger.info(f"--- Done Google News RSS: {len(results)} tenders ---")
    return results


# ── SOURCE 2: CPPP (Central Public Procurement Portal - Govt of India) ────────
def scrape_cppp() -> List[Dict]:
    """CPPP is a government portal - generally accessible from cloud servers"""
    results = []
    base = "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata"
    try:
        r = safe_get(base, timeout=20)
        if not r:
            logger.info("--- Done CPPP: blocked/unavailable ---")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr")
        count = 0
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            title = cols[0].get_text(strip=True)
            org = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            link_tag = cols[0].find("a")
            link = "https://eprocure.gov.in" + link_tag["href"] if link_tag and link_tag.get("href") else ""
            if keyword_match(f"{title} {org}"):
                results.append({
                    "title": title,
                    "url": link,
                    "source": "CPPP (eprocure.gov.in)",
                    "published": "",
                    "bid_no": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    "org": org,
                    "value": "",
                })
                count += 1
        logger.info(f"  CPPP: {count} matching tenders from {len(rows)} rows")
    except Exception as e:
        logger.error(f"CPPP error: {e}")
    logger.info(f"--- Done CPPP: {len(results)} tenders ---")
    return results


# ── SOURCE 3: BidAssist public search ─────────────────────────────────────────
def scrape_bidassist() -> List[Dict]:
    results = []
    search_terms = ["e-learning", "iGOT", "content-development", "augmented-reality", "LMS"]
    for term in search_terms:
        url = f"https://bidassist.com/tenders/{term}"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".tender-card, .bid-card, article, .tender-item, [class*='tender']")
        logger.info(f"  BidAssist [{term}]: {len(cards)} cards found")
        for card in cards:
            title = card.get_text(strip=True)[:200]
            link_tag = card.find("a")
            link = link_tag["href"] if link_tag and link_tag.get("href") else url
            if not link.startswith("http"):
                link = "https://bidassist.com" + link
            if keyword_match(title) and len(title) > 20:
                results.append({
                    "title": title,
                    "url": link,
                    "source": "BidAssist",
                    "published": "",
                    "bid_no": "",
                    "org": "",
                    "value": "",
                })
        time.sleep(3)
    logger.info(f"--- Done BidAssist: {len(results)} tenders ---")
    return results


# ── SOURCE 4: TendersOnTime ───────────────────────────────────────────────────
def scrape_tendersontime() -> List[Dict]:
    results = []
    for kw in ["e-learning", "iGOT", "content development", "augmented reality"]:
        encoded = urllib.parse.quote(kw)
        url = f"https://www.tendersontime.com/search-tenders/?keyword={encoded}&country=India"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".tender-title, .tender-name, h3 a, h2 a, [class*='title'] a")
        logger.info(f"  TendersOnTime [{kw}]: {len(items)} items")
        for item in items:
            title = item.get_text(strip=True)
            link = item.get("href", url)
            if not link.startswith("http"):
                link = "https://www.tendersontime.com" + link
            if keyword_match(title) and len(title) > 20:
                results.append({
                    "title": title,
                    "url": link,
                    "source": "TendersOnTime",
                    "published": "",
                    "bid_no": "",
                    "org": "",
                    "value": "",
                })
        time.sleep(2)
    logger.info(f"--- Done TendersOnTime: {len(results)} tenders ---")
    return results


# ── SOURCE 5: NationalTenders ─────────────────────────────────────────────────
def scrape_nationaltenders() -> List[Dict]:
    results = []
    for kw in ["e-learning", "iGOT content", "augmented reality", "LMS"]:
        encoded = urllib.parse.quote(kw)
        url = f"https://www.nationaltenders.in/tenders/search?q={encoded}"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("a[href*='tender'], .tender-title, h3, h4")
        logger.info(f"  NationalTenders [{kw}]: {len(items)} items")
        for item in items:
            title = item.get_text(strip=True)
            link = item.get("href", url) if item.name == "a" else url
            if not link.startswith("http"):
                link = "https://www.nationaltenders.in" + link
            if keyword_match(title) and len(title) > 20:
                results.append({
                    "title": title,
                    "url": link,
                    "source": "NationalTenders",
                    "published": "",
                    "bid_no": "",
                    "org": "",
                    "value": "",
                })
        time.sleep(2)
    logger.info(f"--- Done NationalTenders: {len(results)} tenders ---")
    return results


# ── SOURCE 6: DuckDuckGo HTML search ─────────────────────────────────────────
def scrape_duckduckgo() -> List[Dict]:
    results = []
    queries = [
        'GeM bid 2026 "e-learning" OR "iGOT" OR "content development" site:gem.gov.in OR site:bidassist.com',
        'GeM tender 2026 "augmented reality" OR "virtual reality" OR "immersive learning"',
        '"GEM/2026" "content development" OR "e-learning" OR "LMS" filetype:pdf OR site:gov.in',
    ]
    for q in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select(".result__title a, .result__a")
        logger.info(f"  DuckDuckGo [{q[:50]}]: {len(links)} results")
        for link in links:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if keyword_match(title) and len(title) > 20:
                results.append({
                    "title": title,
                    "url": href,
                    "source": "DuckDuckGo",
                    "published": "",
                    "bid_no": "",
                    "org": "",
                    "value": "",
                })
        time.sleep(4)
    logger.info(f"--- Done DuckDuckGo: {len(results)} tenders ---")
    return results


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────
def scrape_all_portals() -> List[Dict]:
    all_tenders = []

    sources = [
        ("Google News RSS", scrape_google_news_rss),
        ("CPPP", scrape_cppp),
        ("BidAssist", scrape_bidassist),
        ("TendersOnTime", scrape_tendersontime),
        ("NationalTenders", scrape_nationaltenders),
        ("DuckDuckGo Search", scrape_duckduckgo),
    ]

    for name, fn in sources:
        logger.info(f"--- Starting: {name} ---")
        try:
            results = fn()
            all_tenders.extend(results)
        except Exception as e:
            logger.error(f"Source {name} completely failed: {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for t in all_tenders:
        key = t["title"].strip().lower()[:80]
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique.append(t)

    logger.info(f"=== GRAND TOTAL unique tenders: {len(unique)} ===")
    return unique
