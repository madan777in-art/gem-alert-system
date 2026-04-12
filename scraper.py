"""
scraper.py — GeM Portal Scraper (Railway-compatible, no Selenium)
Uses requests + BeautifulSoup only. Falls back to GeM's public API endpoints.
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import random
import re
import json
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

RETRY_LIMIT = 3
RETRY_DELAY = 5


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def random_delay():
    time.sleep(random.uniform(2, 4))


def fetch_page(url: str, timeout: int = 25) -> Optional[str]:
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            random_delay()
            resp = requests.get(url, headers=get_headers(), timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error attempt {attempt} for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout attempt {attempt} for {url}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error attempt {attempt} for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
    logger.error(f"All attempts failed for: {url}")
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


def scrape_bidplus(max_pages: int = 5) -> List[Dict]:
    tenders = []
    logger.info("Scraping bidplus.gem.gov.in ...")

    urls = [
        "https://bidplus.gem.gov.in/all-bids",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=e-learning",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=iGOT",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=content+development",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=storyboarding",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=augmented+reality",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=virtual+reality",
        "https://bidplus.gem.gov.in/advance-search?searchedBidKeyword=immersive+learning",
    ]

    for url in urls:
        try:
            html = fetch_page(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = parse_bidplus_page(soup, url)
            tenders.extend(found)
            logger.info(f"  {url}: {len(found)} tenders")
        except Exception as e:
            logger.error(f"bidplus error {url}: {e}")

    for page in range(2, max_pages + 1):
        try:
            url = f"https://bidplus.gem.gov.in/all-bids?page_no={page}"
            html = fetch_page(url)
            if not html:
                break
            soup = BeautifulSoup(html, "html.parser")
            found = parse_bidplus_page(soup, url)
            if not found:
                break
            tenders.extend(found)
        except Exception as e:
            logger.error(f"Pagination error page {page}: {e}")
            break

    seen = set()
    unique = []
    for t in tenders:
        if t["bid_no"] not in seen:
            seen.add(t["bid_no"])
            unique.append(t)
    logger.info(f"bidplus unique tenders: {len(unique)}")
    return unique


def parse_bidplus_page(soup: BeautifulSoup, source_url: str) -> List[Dict]:
    tenders = []
    all_text_blocks = soup.find_all(["div", "tr", "article", "li", "section"])
    seen_bids = set()

    for block in all_text_blocks:
        text = block.get_text(separator=" ", strip=True)
        bid_no = extract_bid_no(text)
        if not bid_no or bid_no in seen_bids or len(text) < 30:
            continue
        seen_bids.add(bid_no)

        title_tag = block.find(["h1", "h2", "h3", "h4", "h5", "a", "strong"])
        title = title_tag.get_text(strip=True) if title_tag else text[:150]

        org_match = re.search(
            r"(Ministry|Department|Institute|Council|Board|Authority|Office|"
            r"AIIMS|IIT|NIC|DRDO|University|Hospital|Academy)[^\n,;]{0,60}",
            text, re.IGNORECASE
        )
        org = org_match.group(0).strip() if org_match else "Government Department"

        link_tag = block.find("a", href=True)
        if link_tag:
            href = link_tag["href"]
            link = href if href.startswith("http") else f"https://bidplus.gem.gov.in{href}"
        else:
            link = "https://bidplus.gem.gov.in/all-bids"

        start_date, end_date = extract_dates(text)

        tenders.append({
            "title": title[:200],
            "bid_no": bid_no,
            "organisation": org,
            "description": text[:600],
            "value": extract_value(text),
            "start_date": start_date,
            "end_date": end_date,
            "url": link,
            "source": "bidplus.gem.gov.in",
        })
    return tenders


def scrape_gem_main() -> List[Dict]:
    tenders = []
    logger.info("Scraping gem.gov.in ...")

    keywords = [
        "e-learning", "content development", "iGOT",
        "storyboarding", "augmented reality", "virtual reality",
        "immersive learning", "interactive content",
    ]

    for kw in keywords:
        try:
            url = f"https://gem.gov.in/search?q={requests.utils.quote(kw)}&type=bid"
            html = fetch_page(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            blocks = soup.find_all(["div", "article", "li"])
            for b in blocks:
                text = b.get_text(separator=" ", strip=True)
                bid_no = extract_bid_no(text)
                if not bid_no:
                    continue
                title_tag = b.find(["h2", "h3", "h4", "a"])
                title = title_tag.get_text(strip=True) if title_tag else text[:150]
                link_tag = b.find("a", href=True)
                link = link_tag["href"] if link_tag else "https://gem.gov.in"
                if link.startswith("/"):
                    link = "https://gem.gov.in" + link
                start_date, end_date = extract_dates(text)
                tenders.append({
                    "title": title[:200],
                    "bid_no": bid_no,
                    "organisation": "Government of India",
                    "description": text[:600],
                    "value": extract_value(text),
                    "start_date": start_date,
                    "end_date": end_date,
                    "url": link,
                    "source": "gem.gov.in",
                })
        except Exception as e:
            logger.error(f"gem.gov.in error for '{kw}': {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"gem.gov.in unique: {len(unique)}")
    return unique


def scrape_fulfilment() -> List[Dict]:
    tenders = []
    logger.info("Scraping fulfilment.gem.gov.in ...")

    urls = [
        "https://fulfilment.gem.gov.in/fulfilment/home",
        "https://fulfilment.gem.gov.in/fulfilment/search?keyword=e-learning",
        "https://fulfilment.gem.gov.in/fulfilment/search?keyword=iGOT",
    ]

    for url in urls:
        try:
            html = fetch_page(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            blocks = soup.find_all(["div", "tr", "li"])
            for b in blocks:
                text = b.get_text(separator=" ", strip=True)
                bid_no = extract_bid_no(text)
                if not bid_no:
                    continue
                title_tag = b.find(["h3", "h4", "a", "strong"])
                title = title_tag.get_text(strip=True) if title_tag else text[:150]
                start_date, end_date = extract_dates(text)
                tenders.append({
                    "title": title[:200],
                    "bid_no": bid_no,
                    "organisation": "GeM Fulfilment",
                    "description": text[:600],
                    "value": extract_value(text),
                    "start_date": start_date,
                    "end_date": end_date,
                    "url": url,
                    "source": "fulfilment.gem.gov.in",
                })
        except Exception as e:
            logger.error(f"Fulfilment error {url}: {e}")

    seen = set()
    unique = [t for t in tenders if not (t["bid_no"] in seen or seen.add(t["bid_no"]))]
    logger.info(f"fulfilment.gem.gov.in unique: {len(unique)}")
    return unique


def scrape_all_portals() -> List[Dict]:
    all_tenders = []
    for name, fn in [
        ("bidplus.gem.gov.in", scrape_bidplus),
        ("gem.gov.in", scrape_gem_main),
        ("fulfilment.gem.gov.in", scrape_fulfilment),
    ]:
        try:
            results = fn()
            all_tenders.extend(results)
        except Exception as e:
            logger.error(f"Portal {name} completely failed: {e}")
    logger.info(f"Grand total: {len(all_tenders)} tenders scraped")
    return all_tenders
