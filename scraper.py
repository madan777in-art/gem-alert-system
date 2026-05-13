"""
scraper.py — Enhanced Tender Scraper v5
Sources:
  DIRECT GOVT:  GeM Bid API, CPPP/eProcure API, eTenders NIC
  AGGREGATORS:  BidAssist, TendersOnTime, TenderDetail, NationalTenders, FirstTender, DuckDuckGo
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import json
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def safe_get(url, timeout=20, params=None, extra_headers=None):
    try:
        hdrs = dict(HEADERS)
        if extra_headers:
            hdrs.update(extra_headers)
        r = SESSION.get(url, timeout=timeout, params=params, headers=hdrs)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.warning(f"GET failed [{url}]: {e}")
        return None


# ─────────────────────────────────────────────
# SOURCE 1 — GeM BidPlus PUBLIC API
# GeM exposes a JSON search API used by their own frontend
# ─────────────────────────────────────────────
def scrape_gem_api(keywords):
    tenders = []
    logger.info("--- GeM BidPlus API ---")
    base_url = "https://bidplus.gem.gov.in/all-bids"

    # GeM has a public bid listing — scrape the HTML page
    # They render bids in HTML cards accessible without login
    try:
        r = safe_get(base_url, timeout=25)
        if not r:
            logger.warning("GeM BidPlus: blocked or unreachable from cloud IP")
            return tenders

        soup = BeautifulSoup(r.text, "html.parser")
        # GeM bid cards have class 'bid_no_hover' or similar
        bid_cards = soup.find_all("div", class_=lambda c: c and "bid" in c.lower())

        for card in bid_cards[:50]:
            text = card.get_text(" ", strip=True)
            title = text[:200] if text else ""
            link_tag = card.find("a", href=True)
            link = "https://bidplus.gem.gov.in" + link_tag["href"] if link_tag else base_url
            if title:
                tenders.append({
                    "title": title,
                    "link": link,
                    "source": "GeM BidPlus",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        logger.info(f"GeM BidPlus: {len(tenders)} bids scraped")
    except Exception as e:
        logger.warning(f"GeM BidPlus error: {e}")

    return tenders


# ─────────────────────────────────────────────
# SOURCE 2 — CPPP / eProcure.gov.in
# Central Public Procurement Portal — official GoI tender portal
# ─────────────────────────────────────────────
def scrape_cppp(keywords):
    tenders = []
    logger.info("--- CPPP / eProcure.gov.in ---")

    # CPPP has a public active tenders page
    url = "https://eprocure.gov.in/eprocure/app"
    params = {
        "component": "$DirectLink",
        "page": "FrontEndLatestActiveTenders",
        "service": "direct",
    }

    try:
        r = safe_get(url, params=params, timeout=25)
        if not r:
            logger.warning("CPPP: not reachable")
            return tenders

        soup = BeautifulSoup(r.text, "html.parser")
        # CPPP renders tenders in a table
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:
                title = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                link_tag = cols[1].find("a", href=True)
                link = link_tag["href"] if link_tag else url
                if not link.startswith("http"):
                    link = "https://eprocure.gov.in" + link
                dept = cols[0].get_text(strip=True) if cols else ""
                if title and len(title) > 10:
                    tenders.append({
                        "title": f"{title} [{dept}]",
                        "link": link,
                        "source": "CPPP / eProcure",
                        "published": datetime.now().strftime("%d-%m-%Y"),
                    })

        logger.info(f"CPPP: {len(tenders)} tenders scraped")
    except Exception as e:
        logger.warning(f"CPPP error: {e}")

    return tenders


# ─────────────────────────────────────────────
# SOURCE 3 — eTenders NIC (etenders.gov.in)
# NIC's national e-procurement system
# ─────────────────────────────────────────────
def scrape_etenders_nic(keywords):
    tenders = []
    logger.info("--- eTenders NIC (etenders.gov.in) ---")
    url = "https://etenders.gov.in/eprocure/app"
    params = {
        "component": "$DirectLink",
        "page": "FrontEndLatestActiveTenders",
        "service": "direct",
    }
    try:
        r = safe_get(url, params=params, timeout=25)
        if not r:
            logger.warning("eTenders NIC: not reachable")
            return tenders

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                title = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                link_tag = cols[1].find("a", href=True)
                link = link_tag["href"] if link_tag else url
                if not link.startswith("http"):
                    link = "https://etenders.gov.in" + link
                if title and len(title) > 10:
                    tenders.append({
                        "title": title,
                        "link": link,
                        "source": "eTenders NIC",
                        "published": datetime.now().strftime("%d-%m-%Y"),
                    })
        logger.info(f"eTenders NIC: {len(tenders)} tenders scraped")
    except Exception as e:
        logger.warning(f"eTenders NIC error: {e}")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 4 — BidAssist (aggregator)
# ─────────────────────────────────────────────
def scrape_bidassist(keywords):
    tenders = []
    logger.info("--- BidAssist ---")
    for kw in keywords[:5]:
        url = f"https://bidassist.com/tenders?q={requests.utils.quote(kw)}&country=India"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", class_=lambda c: c and "tender" in c.lower())
        for card in cards[:20]:
            title_tag = card.find(["h2", "h3", "a"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            link_tag = card.find("a", href=True)
            link = link_tag["href"] if link_tag else url
            if not link.startswith("http"):
                link = "https://bidassist.com" + link
            if title:
                tenders.append({
                    "title": title,
                    "link": link,
                    "source": "BidAssist",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        time.sleep(1)
    logger.info(f"BidAssist: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 5 — TendersOnTime
# ─────────────────────────────────────────────
def scrape_tendersontime(keywords):
    tenders = []
    logger.info("--- TendersOnTime ---")
    urls = [
        "https://www.tendersontime.com/indiaproducts/indian-e-learning-tenders-1546/",
        "https://www.tendersontime.com/indiaproducts/indian-learning-and-development-tenders-3920/",
    ]
    for url in urls:
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all(["h3", "h4", "li", "div"], class_=lambda c: c and ("tender" in str(c).lower() or "result" in str(c).lower()))
        for item in items[:30]:
            title = item.get_text(strip=True)
            link_tag = item.find("a", href=True)
            link = link_tag["href"] if link_tag else url
            if not link.startswith("http"):
                link = "https://www.tendersontime.com" + link
            if title and len(title) > 15:
                tenders.append({
                    "title": title,
                    "link": link,
                    "source": "TendersOnTime",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        time.sleep(1)
    logger.info(f"TendersOnTime: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 6 — TenderDetail
# ─────────────────────────────────────────────
def scrape_tenderdetail(keywords):
    tenders = []
    logger.info("--- TenderDetail ---")
    urls = [
        "https://www.tenderdetail.com/Indian-tender/e-learning-content-development-tenders",
        "https://www.tenderdetail.com/Indian-tender/e-learning-tenders",
        "https://www.tenderdetail.com/Indian-tender/immersive-tenders-tenders",
    ]
    for url in urls:
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("div", class_=lambda c: c and "tender" in str(c).lower())
        for row in rows[:30]:
            title = row.get_text(" ", strip=True)[:250]
            link_tag = row.find("a", href=True)
            link = link_tag["href"] if link_tag else url
            if not link.startswith("http"):
                link = "https://www.tenderdetail.com" + link
            if title and len(title) > 20:
                tenders.append({
                    "title": title,
                    "link": link,
                    "source": "TenderDetail",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        time.sleep(1)
    logger.info(f"TenderDetail: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 7 — NationalTenders
# ─────────────────────────────────────────────
def scrape_nationaltenders(keywords):
    tenders = []
    logger.info("--- NationalTenders ---")
    for kw in keywords[:4]:
        url = f"https://www.nationaltenders.com/tender/search?q={requests.utils.quote(kw)}"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all(["h2", "h3", "a"], class_=lambda c: c and "tender" in str(c).lower())
        for item in items[:20]:
            title = item.get_text(strip=True)
            link_tag = item if item.name == "a" else item.find("a", href=True)
            link = link_tag["href"] if link_tag and link_tag.has_attr("href") else url
            if not link.startswith("http"):
                link = "https://www.nationaltenders.com" + link
            if title and len(title) > 15:
                tenders.append({
                    "title": title,
                    "link": link,
                    "source": "NationalTenders",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        time.sleep(1)
    logger.info(f"NationalTenders: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 8 — FirstTender
# ─────────────────────────────────────────────
def scrape_firsttender(keywords):
    tenders = []
    logger.info("--- FirstTender ---")
    for kw in keywords[:4]:
        url = f"https://www.firsttender.com/tender/search-result.aspx?SearchFor={requests.utils.quote(kw)}"
        r = safe_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("td")
        for td in rows:
            text = td.get_text(strip=True)
            link_tag = td.find("a", href=True)
            link = link_tag["href"] if link_tag else url
            if not link.startswith("http"):
                link = "https://www.firsttender.com" + link
            if text and len(text) > 20:
                tenders.append({
                    "title": text[:250],
                    "link": link,
                    "source": "FirstTender",
                    "published": datetime.now().strftime("%d-%m-%Y"),
                })
        time.sleep(1)
    logger.info(f"FirstTender: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# SOURCE 9 — DuckDuckGo HTML search
# Catches tenders on GeM / CPPP / govt sites via web search
# ─────────────────────────────────────────────
def scrape_duckduckgo(keywords):
    tenders = []
    logger.info("--- DuckDuckGo Search (GeM + CPPP site search) ---")

    search_queries = [
        f'site:gem.gov.in "{keywords[0]}" tender',
        f'site:eprocure.gov.in "{keywords[0]}" tender',
        f'"{keywords[0]}" "{keywords[1]}" government tender India 2026',
        f'iGOT "e-learning content development" tender 2026',
        f'LMS "learning management system" government tender India',
        f'"AR VR" OR "immersive learning" government tender India 2026',
    ]

    for query in search_queries[:4]:
        url = "https://html.duckduckgo.com/html/"
        try:
            r = requests.post(
                url,
                data={"q": query, "b": "", "kl": "in-en"},
                headers=HEADERS,
                timeout=20
            )
            soup = BeautifulSoup(r.text, "html.parser")
            results = soup.find_all("div", class_="result__body")
            for res in results[:8]:
                title_tag = res.find("a", class_="result__a")
                snippet_tag = res.find("a", class_="result__snippet")
                title = title_tag.get_text(strip=True) if title_tag else ""
                link = title_tag["href"] if title_tag and title_tag.has_attr("href") else ""
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                combined = f"{title} {snippet}"
                if title and len(title) > 10:
                    tenders.append({
                        "title": combined[:300],
                        "link": link,
                        "source": "Web Search (GeM/CPPP)",
                        "published": datetime.now().strftime("%d-%m-%Y"),
                    })
            time.sleep(2)
        except Exception as e:
            logger.warning(f"DuckDuckGo query error: {e}")

    logger.info(f"DuckDuckGo: {len(tenders)} results")
    return tenders


# ─────────────────────────────────────────────
# MASTER SCRAPER — calls all sources
# ─────────────────────────────────────────────
def scrape_all(keywords):
    all_tenders = []

    sources = [
        ("GeM BidPlus API",     scrape_gem_api),
        ("CPPP / eProcure",     scrape_cppp),
        ("eTenders NIC",        scrape_etenders_nic),
        ("BidAssist",           scrape_bidassist),
        ("TendersOnTime",       scrape_tendersontime),
        ("TenderDetail",        scrape_tenderdetail),
        ("NationalTenders",     scrape_nationaltenders),
        ("FirstTender",         scrape_firsttender),
        ("DuckDuckGo Search",   scrape_duckduckgo),
    ]

    for name, fn in sources:
        try:
            results = fn(keywords)
            all_tenders.extend(results)
            logger.info(f"✓ {name}: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ {name} crashed: {e}")

    logger.info(f"=== GRAND TOTAL scraped: {len(all_tenders)} ===")
    return all_tenders
