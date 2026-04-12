"""
scraper.py — GeM Portal Scraper
Scrapes gem.gov.in, bidplus.gem.gov.in, and fulfilment.gem.gov.in
Falls back to Selenium for JS-rendered pages.
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import random
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ── User-Agent pool ──────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

RETRY_LIMIT = 3
RETRY_DELAY = 5  # seconds


def get_headers() -> Dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def random_delay():
    time.sleep(random.uniform(2, 5))


# ── Selenium fallback ─────────────────────────────────────────────────────────
def get_page_with_selenium(url: str) -> Optional[str]:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)

        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)
            html = driver.page_source
            return html
        finally:
            driver.quit()

    except Exception as e:
        logger.error(f"Selenium failed for {url}: {e}")
        return None


# ── Generic HTTP fetch with retry ─────────────────────────────────────────────
def fetch_page(url: str, use_selenium_fallback: bool = True) -> Optional[str]:
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            random_delay()
            response = requests.get(url, headers=get_headers(), timeout=20)
            response.raise_for_status()

            # Check if page is JS-rendered (empty body signals JS needed)
            if len(response.text.strip()) < 500 and use_selenium_fallback:
                logger.info(f"Page appears JS-rendered, switching to Selenium: {url}")
                return get_page_with_selenium(url)

            return response.text

        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error on attempt {attempt} for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt} for {url}: {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)

    # All retries failed — try Selenium as last resort
    if use_selenium_fallback:
        logger.info(f"All HTTP attempts failed, trying Selenium for: {url}")
        return get_page_with_selenium(url)

    logger.error(f"Failed to fetch {url} after {RETRY_LIMIT} attempts")
    return None


# ── Portal 1: bidplus.gem.gov.in/all-bids ─────────────────────────────────────
def scrape_bidplus(max_pages: int = 10) -> List[Dict]:
    tenders = []
    base_url = "https://bidplus.gem.gov.in/all-bids"

    logger.info("Scraping bidplus.gem.gov.in ...")

    # Try the direct API endpoint first
    api_url = "https://bidplus.gem.gov.in/all-bids"
    html = fetch_page(api_url)

    if not html:
        logger.error("Could not fetch bidplus.gem.gov.in")
        return tenders

    for page in range(1, max_pages + 1):
        try:
            if page == 1:
                page_html = html
            else:
                page_url = f"https://bidplus.gem.gov.in/all-bids?page_no={page}"
                page_html = fetch_page(page_url)
                if not page_html:
                    break

            soup = BeautifulSoup(page_html, "html.parser")

            # GeM bid cards — adjust selectors based on actual page structure
            bid_cards = soup.find_all("div", class_=lambda c: c and (
                "bid-card" in c or "card" in c or "bid_no" in c or "tender" in c.lower()
            ))

            # Fallback: look for any table rows or list items
            if not bid_cards:
                bid_cards = soup.find_all("tr")

            if not bid_cards:
                # Try finding by common GeM HTML patterns
                bid_cards = soup.select(".bid-list-item, .tender-item, .bid_card, [data-bid-no]")

            if not bid_cards and page > 1:
                logger.info(f"No more bid cards found at page {page}, stopping.")
                break

            page_count = 0
            for card in bid_cards:
                tender = parse_bidplus_card(card, page_html)
                if tender:
                    tenders.append(tender)
                    page_count += 1

            logger.info(f"bidplus page {page}: found {page_count} tenders")

            if page_count == 0:
                break

        except Exception as e:
            logger.error(f"Error parsing bidplus page {page}: {e}")
            break

    logger.info(f"bidplus total: {len(tenders)} tenders scraped")
    return tenders


def parse_bidplus_card(card, full_html: str = "") -> Optional[Dict]:
    try:
        text = card.get_text(separator=" ", strip=True)
        if len(text) < 10:
            return None

        # Extract bid number (pattern: GEM/YEAR/B/NUMBER)
        import re
        bid_no_match = re.search(r"GEM/\d{4}/[A-Z]/\d+", text, re.IGNORECASE)
        bid_no = bid_no_match.group(0) if bid_no_match else ""

        if not bid_no:
            return None

        # Extract title
        title_tag = card.find(["h3", "h4", "h5", "a", "strong", "b"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]

        # Extract organisation
        org = ""
        org_patterns = ["Ministry", "Department", "Organisation", "Institute", "Council", "Authority"]
        for line in text.split():
            if any(p.lower() in line.lower() for p in org_patterns):
                org = line
                break

        # Extract dates
        date_matches = re.findall(r"\d{2}[-/]\d{2}[-/]\d{4}", text)
        start_date = date_matches[0] if len(date_matches) > 0 else "N/A"
        end_date = date_matches[1] if len(date_matches) > 1 else "N/A"

        # Extract value
        value_match = re.search(r"₹[\s]?[\d,]+(?:\.\d+)?(?:\s?(?:Lakh|Cr|Crore|L))?", text, re.IGNORECASE)
        value = value_match.group(0) if value_match else "Not specified"

        # Build direct URL
        url = f"https://bidplus.gem.gov.in/bidding/bid/showbidDocument/{bid_no.replace('/', '_')}"

        return {
            "title": title,
            "bid_no": bid_no,
            "organisation": org or "Government Department",
            "description": text[:500],
            "value": value,
            "start_date": start_date,
            "end_date": end_date,
            "url": url,
            "source": "bidplus.gem.gov.in",
        }

    except Exception as e:
        logger.debug(f"Card parse error: {e}")
        return None


# ── Portal 2: gem.gov.in ───────────────────────────────────────────────────────
def scrape_gem_main() -> List[Dict]:
    tenders = []
    logger.info("Scraping gem.gov.in ...")

    # GeM main portal search for services
    search_urls = [
        "https://gem.gov.in/search?q=e-learning&type=bid",
        "https://gem.gov.in/search?q=content+development&type=bid",
        "https://gem.gov.in/search?q=iGOT&type=bid",
        "https://gem.gov.in/search?q=storyboarding&type=bid",
    ]

    for url in search_urls:
        try:
            html = fetch_page(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            results = soup.find_all("div", class_=lambda c: c and (
                "result" in str(c).lower() or "tender" in str(c).lower() or "bid" in str(c).lower()
            ))

            for r in results:
                tender = parse_gem_result(r)
                if tender:
                    tenders.append(tender)

        except Exception as e:
            logger.error(f"Error scraping gem.gov.in search {url}: {e}")

    logger.info(f"gem.gov.in total: {len(tenders)} tenders scraped")
    return tenders


def parse_gem_result(element) -> Optional[Dict]:
    try:
        import re
        text = element.get_text(separator=" ", strip=True)
        if len(text) < 10:
            return None

        bid_no_match = re.search(r"GEM/\d{4}/[A-Z]/\d+", text, re.IGNORECASE)
        bid_no = bid_no_match.group(0) if bid_no_match else f"GEM-{hash(text) % 999999}"

        title_tag = element.find(["h2", "h3", "h4", "a"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]

        link_tag = element.find("a", href=True)
        url = link_tag["href"] if link_tag else "https://gem.gov.in"
        if url.startswith("/"):
            url = "https://gem.gov.in" + url

        return {
            "title": title,
            "bid_no": bid_no,
            "organisation": "Government of India",
            "description": text[:500],
            "value": "Not specified",
            "start_date": "N/A",
            "end_date": "N/A",
            "url": url,
            "source": "gem.gov.in",
        }

    except Exception as e:
        logger.debug(f"gem.gov.in parse error: {e}")
        return None


# ── Portal 3: fulfilment.gem.gov.in ──────────────────────────────────────────
def scrape_fulfilment() -> List[Dict]:
    tenders = []
    logger.info("Scraping fulfilment.gem.gov.in ...")

    url = "https://fulfilment.gem.gov.in/fulfilment/home"
    html = fetch_page(url)

    if not html:
        logger.error("Could not fetch fulfilment.gem.gov.in")
        return tenders

    try:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all(["div", "tr", "li"], class_=lambda c: c and (
            "order" in str(c).lower() or "tender" in str(c).lower() or "bid" in str(c).lower()
        ))

        for item in items:
            tender = parse_fulfilment_item(item)
            if tender:
                tenders.append(tender)

    except Exception as e:
        logger.error(f"Error parsing fulfilment.gem.gov.in: {e}")

    logger.info(f"fulfilment.gem.gov.in total: {len(tenders)} tenders scraped")
    return tenders


def parse_fulfilment_item(element) -> Optional[Dict]:
    try:
        import re
        text = element.get_text(separator=" ", strip=True)
        if len(text) < 10:
            return None

        bid_no_match = re.search(r"GEM/\d{4}/[A-Z]/\d+", text, re.IGNORECASE)
        bid_no = bid_no_match.group(0) if bid_no_match else None
        if not bid_no:
            return None

        title_tag = element.find(["h3", "h4", "a", "strong"])
        title = title_tag.get_text(strip=True) if title_tag else text[:120]

        return {
            "title": title,
            "bid_no": bid_no,
            "organisation": "GeM Fulfilment",
            "description": text[:500],
            "value": "Not specified",
            "start_date": "N/A",
            "end_date": "N/A",
            "url": f"https://fulfilment.gem.gov.in/fulfilment/home",
            "source": "fulfilment.gem.gov.in",
        }

    except Exception as e:
        logger.debug(f"Fulfilment parse error: {e}")
        return None


# ── Master scrape function ────────────────────────────────────────────────────
def scrape_all_portals() -> List[Dict]:
    all_tenders = []

    portals = [
        ("bidplus.gem.gov.in", scrape_bidplus),
        ("gem.gov.in", scrape_gem_main),
        ("fulfilment.gem.gov.in", scrape_fulfilment),
    ]

    for name, scrape_fn in portals:
        try:
            logger.info(f"Starting scrape: {name}")
            results = scrape_fn()
            all_tenders.extend(results)
            logger.info(f"Completed {name}: {len(results)} tenders")
        except Exception as e:
            logger.error(f"Portal {name} scrape failed: {e}")

    logger.info(f"Total tenders scraped across all portals: {len(all_tenders)}")
    return all_tenders
