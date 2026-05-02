"""
emailer.py — HTML Email Alerts
"""
import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict
from matcher import highlight_keywords

logger = logging.getLogger(__name__)

SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL    = os.environ.get("FROM_EMAIL", SMTP_USER)
TO_EMAIL      = os.environ.get("TO_EMAIL", "madan78au@hotmail.com")

STYLE = """
<style>
body{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0}
.w{max-width:680px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.h{background:#1a3c6e;color:#fff;padding:24px 32px}
.h h1{margin:0;font-size:22px}
.h p{margin:6px 0 0;font-size:13px;color:#aac4e8}
.b{padding:28px 32px}
.badge{display:inline-block;background:#e74c3c;color:#fff;font-size:12px;font-weight:bold;padding:4px 12px;border-radius:20px;margin-bottom:16px}
.title{font-size:20px;font-weight:bold;color:#1a3c6e;margin:0 0 16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}
.cell{background:#f8f9fb;border-radius:6px;padding:12px 14px}
.lbl{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.val{font-size:14px;color:#222;font-weight:500}
.st{font-size:13px;font-weight:bold;color:#555;text-transform:uppercase;letter-spacing:.05em;margin:20px 0 8px;border-bottom:1px solid #eee;padding-bottom:6px}
.desc{background:#fafafa;border-left:3px solid #1a3c6e;padding:12px 16px;border-radius:0 6px 6px 0;font-size:14px;color:#333;line-height:1.7}
.kw span{display:inline-block;background:#fff3cd;color:#7d5a00;font-size:12px;font-weight:500;padding:3px 10px;border-radius:12px;margin:3px;border:1px solid #ffc107}
.cta{margin-top:24px;text-align:center}
.cta a{display:inline-block;background:#1a3c6e;color:#fff;text-decoration:none;padding:12px 32px;border-radius:6px;font-size:15px;font-weight:bold}
.ft{background:#f0f4fa;padding:16px 32px;text-align:center;font-size:12px;color:#888}
mark{background:#fff3cd;padding:1px 3px;border-radius:3px}
</style>"""


def build_alert_html(t: Dict) -> str:
    title = t.get("title","Untitled")
    bid_no = t.get("bid_no","N/A")
    organisation = t.get("organisation","N/A")
    desc = highlight_keywords(t.get("description","")[:600], t.get("matched_keywords",[]))
    val = t.get("value","Not specified")
    start = t.get("start_date","N/A")
    end = t.get("end_date","N/A")
    url = t.get("url","https://bidassist.com")
    source = t.get("source","GeM Portal")
    kws = t.get("matched_keywords",[])
    kw_html = "".join(f"<span>{k}</span>" for k in kws)
    now = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    return f"""<!DOCTYPE html><html><head>{STYLE}</head><body>
<div class="w">
  <div class="h"><h1>GeM Tender Alert</h1><p>New matching tender · {now}</p></div>
  <div class="b">
    <span class="badge">NEW TENDER</span>
    <div class="title">{title}</div>
    <div class="grid">
      <div class="cell"><div class="lbl">Bid Number</div><div class="val">{bid_no}</div></div>
      <div class="cell"><div class="lbl">Source Portal</div><div class="val">{source}</div></div>
      <div class="cell"><div class="lbl">Organisation</div><div class="val">{organisation}</div></div>
      <div class="cell"><div class="lbl">Estimated Value</div><div class="val">{val}</div></div>
      <div class="cell"><div class="lbl">Start Date</div><div class="val">{start}</div></div>
      <div class="cell"><div class="lbl">Closing Date</div><div class="val">{end}</div></div>
    </div>
    <div class="st">Keywords Matched</div>
    <div class="kw">{kw_html or "N/A"}</div>
    <div class="st">Scope of Work</div>
    <div class="desc">{desc}</div>
    <div class="cta"><a href="{url}">View Full Tender &rarr;</a></div>
  </div>
  <div class="ft">GeM Alert System &nbsp;|&nbsp; {TO_EMAIL} &nbsp;|&nbsp; {now}</div>
</div></body></html>"""


def build_summary_html(tenders: List[Dict], stats: Dict) -> str:
    now = datetime.now().strftime("%d %b %Y")
    if not tenders:
        rows = "<p style='color:#888;text-align:center;padding:20px'>No new matching tenders in last 24 hours.</p>"
    else:
        rows = "<table style='width:100%;border-collapse:collapse;font-size:13px'>"
        rows += "<tr style='background:#f0f4fa'><th style='padding:8px;text-align:left'>Title</th><th>Bid No</th><th>Source</th><th>Keywords</th></tr>"
        for t in tenders:
            kws = ", ".join(t.get("matched_keywords",[]))
            rows += f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{t.get('title','')[:70]}</td><td style='padding:8px;border-bottom:1px solid #eee'><a href='{t.get('url','')}'>{t.get('bid_no','')}</a></td><td style='padding:8px;border-bottom:1px solid #eee'>{t.get('source','')}</td><td style='padding:8px;border-bottom:1px solid #eee;color:#7d5a00'>{kws[:50]}</td></tr>"
        rows += "</table>"
    return f"""<!DOCTYPE html><html><head>{STYLE}</head><body>
<div class="w">
  <div class="h"><h1>Daily GeM Tender Summary</h1><p>{now} · Automated Report</p></div>
  <div class="b">
    <div class="grid">
      <div class="cell"><div class="lbl">Total tracked</div><div class="val">{stats.get('total_seen',0)}</div></div>
      <div class="cell"><div class="lbl">Alerts sent</div><div class="val">{stats.get('total_alerted',0)}</div></div>
      <div class="cell"><div class="lbl">New today</div><div class="val">{len(tenders)}</div></div>
      <div class="cell"><div class="lbl">Last scrape</div><div class="val">{stats.get('last_scrape','N/A')[:16]}</div></div>
    </div>
    <div class="st">New Tenders (Last 24 Hours)</div>
    {rows}
  </div>
  <div class="ft">GeM Alert System · Daily Digest · {now}</div>
</div></body></html>"""


def send_email(subject: str, html: str, to: str = TO_EMAIL) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials missing in environment variables")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(FROM_EMAIL, [to], msg.as_string())
        logger.info(f"Email sent: {subject[:60]} → {to}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed — check SMTP_USER and SMTP_PASSWORD")
        return False
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


def send_tender_alert(t: Dict) -> bool:
    title = t.get("title","New Tender")[:80]
    bid = t.get("bid_no","")
    return send_email(f"[GeM Alert] {title} — {bid}", build_alert_html(t))


def send_daily_summary(tenders: List[Dict], stats: Dict) -> bool:
    date_str = datetime.now().strftime("%d %b %Y")
    return send_email(f"[GeM Daily Summary] {len(tenders)} new tender(s) — {date_str}",
                      build_summary_html(tenders, stats))


def send_admin_alert(msg: str) -> bool:
    html = f"<div style='font-family:Arial;padding:20px'><h2 style='color:#e74c3c'>Scraper Error</h2><p>{msg}</p><p style='color:#888;font-size:12px'>{datetime.now().isoformat()}</p></div>"
    return send_email("[GeM Alert System] ERROR — Scraper failure", html)
