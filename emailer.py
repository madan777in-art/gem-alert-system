"""
emailer.py — Email Alert System
Sends HTML-formatted instant alerts and daily summaries.
"""

import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Optional
from matcher import highlight_keywords

logger = logging.getLogger(__name__)

# ── Config from .env ──────────────────────────────────────────────────────────
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL    = os.environ.get("FROM_EMAIL", SMTP_USER)
TO_EMAIL      = os.environ.get("TO_EMAIL", "madan78au@hotmail.com")


# ── HTML Templates ────────────────────────────────────────────────────────────
EMAIL_BASE_STYLE = """
<style>
  body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }
  .wrapper { max-width: 680px; margin: 20px auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .header { background: #1a3c6e; color: #fff; padding: 24px 32px; }
  .header h1 { margin: 0; font-size: 22px; }
  .header p { margin: 6px 0 0; font-size: 13px; color: #aac4e8; }
  .body { padding: 28px 32px; }
  .alert-badge { display: inline-block; background: #e74c3c; color: #fff; font-size: 12px; font-weight: bold; padding: 4px 12px; border-radius: 20px; margin-bottom: 16px; }
  .tender-title { font-size: 20px; font-weight: bold; color: #1a3c6e; margin: 0 0 16px; }
  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
  .info-item { background: #f8f9fb; border-radius: 6px; padding: 12px 14px; }
  .info-label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
  .info-value { font-size: 14px; color: #222; font-weight: 500; }
  .section-title { font-size: 13px; font-weight: bold; color: #555; text-transform: uppercase; letter-spacing: 0.05em; margin: 20px 0 8px; border-bottom: 1px solid #eee; padding-bottom: 6px; }
  .desc-box { background: #fafafa; border-left: 3px solid #1a3c6e; padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 14px; color: #333; line-height: 1.7; }
  .keywords { margin: 12px 0; }
  .kw-tag { display: inline-block; background: #fff3cd; color: #7d5a00; font-size: 12px; font-weight: 500; padding: 3px 10px; border-radius: 12px; margin: 3px; border: 1px solid #ffc107; }
  .cta { margin-top: 24px; text-align: center; }
  .cta a { display: inline-block; background: #1a3c6e; color: #fff; text-decoration: none; padding: 12px 32px; border-radius: 6px; font-size: 15px; font-weight: bold; }
  .footer { background: #f0f4fa; padding: 16px 32px; text-align: center; font-size: 12px; color: #888; }
  .divider { border: none; border-top: 1px solid #eee; margin: 20px 0; }
  mark { background: #fff3cd; padding: 1px 3px; border-radius: 3px; }
</style>
"""


def build_instant_alert_html(tender: Dict) -> str:
    """Build HTML body for a single new tender alert."""
    title = tender.get("title", "Untitled Tender")
    bid_no = tender.get("bid_no", "N/A")
    org = tender.get("organisation", "N/A")
    description = tender.get("description", "No description available.")
    value = tender.get("value", "Not specified")
    start_date = tender.get("start_date", "N/A")
    end_date = tender.get("end_date", "N/A")
    url = tender.get("url", "https://bidplus.gem.gov.in/all-bids")
    source = tender.get("source", "GeM Portal")
    keywords = tender.get("matched_keywords", [])

    # Highlight keywords in description
    highlighted_desc = highlight_keywords(description[:600], keywords)

    # Keyword tags HTML
    kw_tags = "".join(f'<span class="kw-tag">{kw}</span>' for kw in keywords)

    now = datetime.now().strftime("%d %b %Y, %I:%M %p IST")

    return f"""<!DOCTYPE html>
<html>
<head>{EMAIL_BASE_STYLE}</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>GeM Tender Alert</h1>
    <p>New matching tender detected · {now}</p>
  </div>
  <div class="body">
    <span class="alert-badge">NEW TENDER</span>
    <div class="tender-title">{title}</div>

    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Bid Number</div>
        <div class="info-value">{bid_no}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Source Portal</div>
        <div class="info-value">{source}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Organisation</div>
        <div class="info-value">{org}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Estimated Value</div>
        <div class="info-value">{value}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Bid Start Date</div>
        <div class="info-value">{start_date}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Bid End / Closing Date</div>
        <div class="info-value">{end_date}</div>
      </div>
    </div>

    <div class="section-title">Keywords Matched</div>
    <div class="keywords">{kw_tags if kw_tags else "N/A"}</div>

    <div class="section-title">Scope of Work / Description</div>
    <div class="desc-box">{highlighted_desc}</div>

    <div class="cta">
      <a href="{url}">View Full Tender on GeM &rarr;</a>
    </div>
  </div>
  <div class="footer">
    This alert was sent by your GeM Tender Alert System &nbsp;|&nbsp; To: {TO_EMAIL}<br>
    Portal: {source} &nbsp;|&nbsp; Alert generated at {now}
  </div>
</div>
</body>
</html>"""


def build_daily_summary_html(tenders: List[Dict], stats: Dict) -> str:
    """Build HTML for daily summary email."""
    now = datetime.now().strftime("%d %b %Y")

    if not tenders:
        tender_rows = "<p style='color:#888;text-align:center;padding:20px;'>No new matching tenders in the last 24 hours.</p>"
    else:
        rows = ""
        for t in tenders:
            kws = ", ".join(t.get("matched_keywords", []))
            rows += f"""
            <tr>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-size:13px;">{t.get('title','')[:80]}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-size:12px;color:#555;">{t.get('bid_no','')}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-size:12px;">{t.get('source','')}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-size:12px;color:#7d5a00;">{kws[:60]}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-size:12px;">
                <a href="{t.get('url','')}" style="color:#1a3c6e;">View</a>
              </td>
            </tr>"""

        tender_rows = f"""
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#f0f4fa;">
              <th style="padding:10px 8px;text-align:left;font-size:12px;color:#555;">Title</th>
              <th style="padding:10px 8px;text-align:left;font-size:12px;color:#555;">Bid No.</th>
              <th style="padding:10px 8px;text-align:left;font-size:12px;color:#555;">Source</th>
              <th style="padding:10px 8px;text-align:left;font-size:12px;color:#555;">Keywords</th>
              <th style="padding:10px 8px;text-align:left;font-size:12px;color:#555;">Link</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html>
<head>{EMAIL_BASE_STYLE}</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Daily GeM Tender Summary</h1>
    <p>{now} · Automated Report · madan78au@hotmail.com</p>
  </div>
  <div class="body">
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Total tenders tracked</div>
        <div class="info-value">{stats.get('total_seen', 0)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Alerts sent (total)</div>
        <div class="info-value">{stats.get('total_alerted', 0)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">New today</div>
        <div class="info-value">{len(tenders)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Last scrape</div>
        <div class="info-value">{stats.get('last_scrape', 'N/A')[:16]}</div>
      </div>
    </div>

    <div class="section-title">New Matching Tenders (Last 24 Hours)</div>
    {tender_rows}

    <div class="cta" style="margin-top:20px;">
      <a href="https://bidplus.gem.gov.in/all-bids">Browse All GeM Bids &rarr;</a>
    </div>
  </div>
  <div class="footer">
    GeM Tender Alert System · Daily digest · {now}
  </div>
</div>
</body>
</html>"""


# ── Send email ────────────────────────────────────────────────────────────────
def send_email(subject: str, html_body: str, to: str = TO_EMAIL) -> bool:
    """Send HTML email via SMTP. Returns True on success."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured in .env")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, [to], msg.as_string())

        logger.info(f"Email sent: {subject[:60]} → {to}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check SMTP_USER and SMTP_PASSWORD in .env")
        return False
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_tender_alert(tender: Dict) -> bool:
    """Send instant alert for a single new tender."""
    title = tender.get("title", "New Tender")[:80]
    bid_no = tender.get("bid_no", "")
    subject = f"[GeM Alert] New Tender: {title} — {bid_no}"
    html = build_instant_alert_html(tender)
    return send_email(subject, html)


def send_daily_summary(tenders: List[Dict], stats: Dict) -> bool:
    """Send the 8 AM daily digest."""
    date_str = datetime.now().strftime("%d %b %Y")
    subject = f"[GeM Daily Summary] {len(tenders)} new tender(s) — {date_str}"
    html = build_daily_summary_html(tenders, stats)
    return send_email(subject, html)


def send_admin_alert(message: str) -> bool:
    """Send an admin alert if the scraper fails repeatedly."""
    subject = "[GeM Alert System] ERROR — Scraper failure detected"
    html = f"""<div style="font-family:Arial;padding:20px;">
    <h2 style="color:#e74c3c;">Scraper Error Alert</h2>
    <p>{message}</p>
    <p style="color:#888;font-size:12px;">Sent at {datetime.now().isoformat()}</p>
    </div>"""
    return send_email(subject, html)
