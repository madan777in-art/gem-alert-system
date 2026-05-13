"""
emailer.py — HTML email alert sender
Sends beautifully formatted tender alerts to madan78au@hotmail.com
"""

import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

SMTP_HOST   = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER   = os.environ.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "madan78au@hotmail.com")

SOURCE_COLORS = {
    "GeM BidPlus":       "#1a237e",
    "CPPP / eProcure":   "#4a148c",
    "eTenders NIC":      "#880e4f",
    "BidAssist":         "#1565c0",
    "TendersOnTime":     "#00695c",
    "TenderDetail":      "#e65100",
    "NationalTenders":   "#4e342e",
    "FirstTender":       "#37474f",
    "Web Search (GeM/CPPP)": "#006064",
}

GOVT_BADGE = {"GeM BidPlus", "CPPP / eProcure", "eTenders NIC", "Web Search (GeM/CPPP)"}


def source_badge(source):
    color = SOURCE_COLORS.get(source, "#555")
    is_govt = source in GOVT_BADGE
    star = " ★ GOVT" if is_govt else ""
    return (
        f'<span style="background:{color};color:#fff;padding:3px 8px;'
        f'border-radius:12px;font-size:11px;font-weight:bold;">'
        f'{source}{star}</span>'
    )


def build_html(tenders, is_daily=False):
    date_str = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    subj_type = "Daily Summary" if is_daily else "INSTANT ALERT"

    # Group by source
    by_source = {}
    for t in tenders:
        src = t.get("source", "Unknown")
        by_source.setdefault(src, []).append(t)

    rows_html = ""
    for src, items in by_source.items():
        color = SOURCE_COLORS.get(src, "#555")
        rows_html += f"""
        <tr>
          <td colspan="3" style="background:{color};color:#fff;padding:8px 12px;
              font-weight:bold;font-size:13px;">
            {'★ GOVT PORTAL — ' if src in GOVT_BADGE else ''}{src} ({len(items)} tenders)
          </td>
        </tr>"""
        for t in items:
            kws = ", ".join(t.get("matched_keywords", []))
            score = t.get("score", 0)
            rows_html += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 12px;vertical-align:top;width:55%;">
            <a href="{t['link']}" style="color:#1a237e;font-weight:bold;
               text-decoration:none;font-size:13px;">{t['title'][:200]}</a>
          </td>
          <td style="padding:10px 8px;vertical-align:top;width:30%;
              font-size:11px;color:#555;">{kws}</td>
          <td style="padding:10px 8px;vertical-align:top;width:15%;
              text-align:center;">
            <span style="background:#e8f5e9;color:#2e7d32;padding:2px 6px;
               border-radius:8px;font-size:11px;font-weight:bold;">
              Score: {score}
            </span>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;">
  <div style="max-width:750px;margin:20px auto;background:#fff;
       border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1a237e,#283593);
         padding:20px 24px;color:#fff;">
      <h2 style="margin:0;font-size:20px;">
        🔔 Tender Alert — {subj_type}
      </h2>
      <p style="margin:6px 0 0;font-size:13px;color:#c5cae9;">
        {date_str} &nbsp;|&nbsp; {len(tenders)} new tender(s) found
      </p>
    </div>

    <!-- Sources Legend -->
    <div style="padding:12px 24px;background:#e8eaf6;font-size:12px;">
      <strong>Sources monitored:</strong> &nbsp;
      GeM BidPlus ★ &nbsp;|&nbsp; CPPP/eProcure ★ &nbsp;|&nbsp; eTenders NIC ★ &nbsp;|&nbsp;
      BidAssist &nbsp;|&nbsp; TendersOnTime &nbsp;|&nbsp; TenderDetail &nbsp;|&nbsp;
      NationalTenders &nbsp;|&nbsp; FirstTender &nbsp;|&nbsp; Web Search
      <br><small style="color:#5c6bc0;">★ = Direct Government Portal</small>
    </div>

    <!-- Tender Table -->
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#666;">
            TENDER TITLE</th>
          <th style="padding:8px 12px;text-align:left;font-size:12px;color:#666;">
            MATCHED KEYWORDS</th>
          <th style="padding:8px 12px;text-align:center;font-size:12px;color:#666;">
            SCORE</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <!-- Footer -->
    <div style="padding:16px 24px;background:#f5f5f5;font-size:11px;color:#888;
         border-top:1px solid #eee;">
      Novac Technology Solutions — Automated Tender Monitor v5<br>
      Monitoring: GeM · CPPP · eTenders NIC · BidAssist · TendersOnTime ·
      TenderDetail · NationalTenders · FirstTender · Web Search
    </div>
  </div>
</body>
</html>"""
    return html


def send_alert(tenders, is_daily=False):
    if not tenders:
        logger.info("No tenders to email")
        return False

    if not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP credentials not set in environment variables")
        return False

    subj_type = "Daily Summary" if is_daily else "INSTANT ALERT"
    subject = (
        f"[Tender Alert] {subj_type} — {len(tenders)} new tender(s) | "
        f"{datetime.now().strftime('%d %b %Y')}"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = ALERT_EMAIL

    html_body = build_html(tenders, is_daily)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        logger.info(f"✅ Email sent to {ALERT_EMAIL} — {len(tenders)} tenders")
        return True
    except Exception as e:
        logger.error(f"❌ Email send failed: {e}")
        return False


def send_startup_email():
    """Send a test email on first startup to confirm the system is live."""
    if not SMTP_USER or not SMTP_PASS:
        return
    subject = "✅ Tender Monitor v5 is LIVE — Novac Technology Solutions"
    html = f"""
    <html><body style="font-family:Arial;padding:20px;">
    <div style="background:#1a237e;color:#fff;padding:20px;border-radius:8px;">
      <h2>🚀 Tender Alert System v5 is Running!</h2>
      <p>Your enhanced tender monitor is now live and watching:</p>
      <ul>
        <li>✅ GeM BidPlus (Direct)</li>
        <li>✅ CPPP / eProcure.gov.in (Direct)</li>
        <li>✅ eTenders NIC (Direct)</li>
        <li>✅ BidAssist</li>
        <li>✅ TendersOnTime</li>
        <li>✅ TenderDetail</li>
        <li>✅ NationalTenders</li>
        <li>✅ FirstTender</li>
        <li>✅ Web Search (GeM + CPPP site search)</li>
      </ul>
      <p>Alerts will arrive at: <strong>madan78au@hotmail.com</strong></p>
      <p>Scan frequency: Every 2 hours | Daily summary: 8:00 AM IST</p>
    </div>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        logger.info("Startup confirmation email sent")
    except Exception as e:
        logger.warning(f"Startup email failed: {e}")
