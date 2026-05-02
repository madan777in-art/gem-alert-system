"""
scraper.py v5 — GeM Tender Scraper
Uses sources confirmed to expose GEM bid numbers in plain HTML.
No GeM direct access (blocked). No JS-rendered pages (no Selenium).
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

KEYWORDS = [
    "e-learning", "elearning", "e learning",
    "content development", "content design", "content designing",
    "storyboarding", "storyboard",
    "interactive content", "interactive content creation",
    "igot", "i-got", "integrated government online training",
    "augmented reality", "virtual reality", "ar/vr", "ar vr",
    "immersive learning", "immersive solutions",
    "level-1", "level-2", "level-3",
    "level 1", "level 2", "level 3",
    "lms", "scorm", "instructional design",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch(url: str, timeout=25) -> Optional[str]:
    for attempt in range(1, 4):
        try:
            time.sleep(random.uniform(2, 4))
            r = requests.get(url, headers=headers(), timeout=timeout)
            r.raise_for_status()
            if len(r.text) > 500:
                return r.text
            logger.warning(f"Too short response from {url}")
            return None
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt} failed [{url}]: {e}")
            if attempt < 3:
                time.sleep(5 * attempt)
    logger.error(f"All attempts failed: {url}")
    return None


def bid_no(text: str) -> Optional[str]:
    m = re.search(r"GEM[/\-]\d{4}[/\-][A-Z][/\-]\d+", text, re.IGNORECASE)
    return m.group(0).upper().replace("-", "/") if m else None


def dates(text: str):
    d = re.findall(r"\d{2}[-/]\d{2}[-/]\d{4}", text)
    return (d[0] if d else "N/A"), (d[1] if len(d) > 1 else "N/A")


def value(text: str) -> str:
    m = re.search(r"(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?(?:\s?(?:Lakh|Lac|L|Cr|Crore))?", text, re.IGNORECASE)
    return m.group(0).strip() if m else "Not specified"


def org(text: str) -> str:
    m = re.search(
        r"(Ministry|Department|Institute|Council|Board|Authority|Office|"
        r"AIIMS|IIT|NIC|DRDO|University|Hospital|Academy|Corporation|"
        r"Commission|Bureau|Directorate|Centre|Center)[^\n,;|]{0,80}",
        text, re.IGNORECASE
    )
    return m.group(0).strip() if m else "Government Department"


def has_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in KEYWORDS)


def tender(bid, title, organisation, desc, val, start, end, url, source) -> Dict:
    return {
        "bid_no": str(bid).strip(),
        "title": str(title).strip()[:200],
        "organisation": str(organisation).strip()[:200],
        "description": str(desc).strip()[:600],
        "value": str(val).strip(),
        "start_date": str(start),
        "end_date": str(end),
        "url": str(url).strip(),
        "source": source,
    }


def extract_from_soup(soup: BeautifulSoup, source: str, base_url: str) -> List[Dict]:
    """Generic extractor — finds any block with a GEM bid number."""
    results = []
    seen = set()
    for block in soup.find_all(["div", "tr", "li", "article", "td", "section"]):
        text = block.get_text(separator=" ", strip=True)
        if len(text) < 20:
            continue
        b = bid_no(text)
        if not b or b in seen:
            continue
        seen.add(b)
        title_tag = block.find(["h1","h2","h3","h4","h5","a","strong","b"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]
        link = block.find("a", href=True)
        if link:
            href = link["href"]
            url = href if href.startswith("http") else ("/".join(base_url.split("/")[:3]) + href)
        else:
            url = base_url
        s, e = dates(text)
        results.append(tender(b, title, org(text), text[:600], value(text), s, e, url, source))
    return results


# ── SOURCE 1: GovTribe (US-based, scrapes Indian tenders, cloud-accessible) ───
def scrape_govtribe() -> List[Dict]:
    results = []
    logger.info("Scraping tenderhunt.in ...")
    urls = [
        "https://tenderhunt.in/?s=e-learning+gem",
        "https://tenderhunt.in/?s=igot+content+development",
        "https://tenderhunt.in/?s=storyboarding+gem",
    ]
    for url in urls:
        try:
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = extract_from_soup(soup, "tenderhunt.in", url)
            keyword_filtered = [t for t in found if has_keyword(t["description"] + t["title"])]
            results.extend(keyword_filtered)
            logger.info(f"  tenderhunt [{url[-30:]}]: {len(keyword_filtered)} tenders")
        except Exception as e:
            logger.error(f"tenderhunt error: {e}")
    return results


# ── SOURCE 2: Tender.guru — large free tender database, India coverage ─────────
def scrape_tenderguru() -> List[Dict]:
    results = []
    logger.info("Scraping tender.guru ...")
    urls = [
        "https://tender.guru/in/search?q=e-learning+content+development",
        "https://tender.guru/in/search?q=igot+storyboarding",
        "https://tender.guru/in/search?q=augmented+reality+virtual+reality+learning",
        "https://tender.guru/in/search?q=content+design+gem",
    ]
    for url in urls:
        try:
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = extract_from_soup(soup, "tender.guru", url)
            # Also look for text blocks mentioning GEM even without bid number format
            if not found:
                # Try alternate parsing for this site
                items = soup.find_all(["article", "div"], class_=re.compile(r"tender|result|item|card", re.I))
                for item in items:
                    text = item.get_text(separator=" ", strip=True)
                    if has_keyword(text) and ("gem" in text.lower() or bid_no(text)):
                        b = bid_no(text) or f"GURU-{abs(hash(text[:50]))}"
                        title_tag = item.find(["h2","h3","h4","a"])
                        title = title_tag.get_text(strip=True) if title_tag else text[:100]
                        link = item.find("a", href=True)
                        link_url = link["href"] if link else url
                        if link_url.startswith("/"):
                            link_url = "https://tender.guru" + link_url
                        s, e = dates(text)
                        found.append(tender(b, title, org(text), text[:600], value(text), s, e, link_url, "tender.guru"))
            results.extend(found)
            logger.info(f"  tender.guru [{url[-35:]}]: {len(found)} tenders")
        except Exception as e:
            logger.error(f"tender.guru error: {e}")
    return results


# ── SOURCE 3: OpenTender.eu India section ─────────────────────────────────────
def scrape_opentender() -> List[Dict]:
    results = []
    logger.info("Scraping tendersindia.com ...")
    urls = [
        "https://www.tendersindia.com/search-result/?s=e-learning",
        "https://www.tendersindia.com/search-result/?s=igot+content",
        "https://www.tendersindia.com/search-result/?s=storyboarding",
        "https://www.tendersindia.com/search-result/?s=augmented+reality",
    ]
    for url in urls:
        try:
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = extract_from_soup(soup, "tendersindia.com", url)
            kw_found = [t for t in found if has_keyword(t["description"] + t["title"])]
            results.extend(kw_found)
            logger.info(f"  tendersindia [{url[-30:]}]: {len(kw_found)} tenders")
        except Exception as e:
            logger.error(f"tendersindia error: {e}")
    return results


# ── SOURCE 4: Merx / Global Tender Search ─────────────────────────────────────
def scrape_etenders() -> List[Dict]:
    results = []
    logger.info("Scraping etenders.in ...")
    urls = [
        "https://www.etenders.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        "https://www.etenders.in/eprocure/app?page=FrontEndTendersByOrganisation&service=page",
    ]
    for url in urls:
        try:
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # Look for table rows with tender data
            rows = soup.find_all("tr")
            seen = set()
            for row in rows:
                text = row.get_text(separator=" ", strip=True)
                if not has_keyword(text) or len(text) < 20:
                    continue
                b = bid_no(text) or f"ET-{abs(hash(text[:50]))}"
                if b in seen:
                    continue
                seen.add(b)
                cells = row.find_all("td")
                title = cells[0].get_text(strip=True) if cells else text[:100]
                link = row.find("a", href=True)
                link_url = link["href"] if link else url
                if link_url.startswith("/"):
                    link_url = "https://www.etenders.in" + link_url
                s, e = dates(text)
                results.append(tender(b, title, org(text), text[:600], value(text), s, e, link_url, "etenders.in"))
            logger.info(f"  etenders [{url[-40:]}]: {len(results)} tenders")
        except Exception as e:
            logger.error(f"etenders error: {e}")
    return results


# ── SOURCE 5: DuckDuckGo HTML — most reliable cloud search ───────────────────
def scrape_duckduckgo() -> List[Dict]:
    results = []
    logger.info("Running DuckDuckGo search ...")

    queries = [
        '"GEM/2026" "e-learning" OR "iGOT" OR "storyboarding" OR "content development"',
        '"GEM/2025" "e-learning" OR "iGOT" OR "content development" OR "storyboarding"',
        '"GEM/2026" "augmented reality" OR "virtual reality" OR "immersive learning"',
        'GeM bid 2026 "e-learning content development" iGOT storyboarding',
        'GeM bid 2026 "content design" OR "interactive content" OR "instructional design"',
    ]

    seen = set()
    for query in queries:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")

            # DuckDuckGo result structure
            result_divs = soup.find_all("div", class_=re.compile(r"result", re.I))
            if not result_divs:
                result_divs = soup.find_all("div", {"data-testid": re.compile(r"result", re.I)})

            for r in result_divs:
                text = r.get_text(separator=" ", strip=True)
                b = bid_no(text)

                # Accept results that either have a GEM bid number OR mention GEM + keyword
                if not b and not ("gem" in text.lower() and has_keyword(text)):
                    continue

                if b and b in seen:
                    continue
                if b:
                    seen.add(b)
                else:
                    b = f"GEM-DDG-{abs(hash(text[:60]))}"

                title_tag = r.find(["h2", "h3", "a"])
                title = title_tag.get_text(strip=True) if title_tag else text[:120]

                link_tag = r.find("a", href=True)
                link = link_tag["href"] if link_tag else "https://bidplus.gem.gov.in/all-bids"
                # DuckDuckGo wraps links — extract actual URL
                if "uddg=" in link:
                    try:
                        from urllib.parse import unquote, urlparse, parse_qs
                        parsed = parse_qs(urlparse(link).query)
                        link = unquote(parsed.get("uddg", [link])[0])
                    except Exception:
                        pass

                s, e = dates(text)
                results.append(tender(
                    b, title, org(text), text[:600],
                    value(text), s, e, link, "GeM Portal"
                ))

            logger.info(f"  DuckDuckGo [{query[:50]}...]: {len(results)} total so far")
            time.sleep(random.uniform(4, 7))  # Be polite to DDG

        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")

    # Deduplicate
    seen2 = set()
    unique = [t for t in results if not (t["bid_no"] in seen2 or seen2.add(t["bid_no"]))]
    return unique


# ── SOURCE 6: Google News RSS — picks up press releases about GeM tenders ─────
def scrape_google_news_rss() -> List[Dict]:
    results = []
    logger.info("Scraping Google News RSS ...")

    queries = [
        "GeM tender e-learning iGOT content development",
        "GeM bid storyboarding augmented reality 2026",
        "government e-marketplace e-learning content development tender",
    ]

    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={quote(q)}&hl=en-IN&gl=IN&ceid=IN:en"
            html = fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "xml")
            items = soup.find_all("item")
            for item in items:
                text = (item.get_text(separator=" ", strip=True))
                if not has_keyword(text):
                    continue
                b = bid_no(text) or f"NEWS-{abs(hash(text[:60]))}"
                title = item.find("title")
                title_text = title.get_text(strip=True) if title else text[:100]
                link = item.find("link")
                link_url = link.get_text(strip=True) if link else ""
                pub_date = item.find("pubDate")
                pub = pub_date.get_text(strip=True) if pub_date else "N/A"
                results.append(tender(
                    b, title_text, "GeM Portal (News)", text[:500],
                    "N/A", pub, "N/A", link_url, "Google News"
                ))
            logger.info(f"  Google News RSS [{q[:40]}]: {len(items)} items checked")
        except Exception as e:
            logger.error(f"Google News RSS error: {e}")

    seen = set()
    unique = [t for t in results if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    return unique


# ── MASTER FUNCTION ───────────────────────────────────────────────────────────
def scrape_all_portals() -> List[Dict]:
    all_tenders = []

    sources = [
        ("DuckDuckGo Search",  scrape_duckduckgo),
        ("Google News RSS",    scrape_google_news_rss),
        ("TendersIndia",       scrape_opentender),
        ("Tender.guru",        scrape_tenderguru),
        ("TenderHunt",         scrape_govtribe),
        ("eTenders",           scrape_etenders),
    ]

    for name, fn in sources:
        try:
            logger.info(f"--- Starting: {name} ---")
            found = fn()
            all_tenders.extend(found)
            logger.info(f"--- Done {name}: {len(found)} tenders ---")
        except Exception as e:
            logger.error(f"Source '{name}' failed completely: {e}")

    # Global dedup by bid_no
    seen = set()
    unique = []
    for t in all_tenders:
        if t["bid_no"] not in seen:
            seen.add(t["bid_no"])
            unique.append(t)

    logger.info(f"=== GRAND TOTAL unique tenders: {len(unique)} ===")
    return unique
