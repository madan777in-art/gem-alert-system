# GeM Tender Alert System

Automated scraper that monitors GeM (Government e-Marketplace) portals every 30 minutes and sends instant email alerts to **madan78au@hotmail.com** whenever a new matching tender is published.

---

## What It Does

- Scrapes **3 GeM portals** every 30 minutes automatically
- Filters tenders by **16 keywords** (E-Learning, iGOT, Storyboarding, AR/VR, etc.)
- Sends **instant HTML email** the moment a new matching tender is found
- **No duplicate alerts** — tracks seen tenders in SQLite database
- Sends a **daily summary at 8:00 AM IST**
- Runs **24/7 unattended** once deployed

---

## Portals Monitored

1. https://gem.gov.in/
2. https://bidplus.gem.gov.in/all-bids
3. https://fulfilment.gem.gov.in/fulfilment/home

---

## Keywords Monitored

- E-Learning, Content Development, Content Design, Content Designing
- Storyboarding, Interactive Content Creation, Interactive Content
- AR/VR Application Development, Augmented Reality, Virtual Reality
- Immersive Learning, Immersive Solutions
- iGOT, Level-1, Level-2, Level-3

---

## Project Structure

```
gem_alert_system/
├── main.py           ← Entry point — run this
├── scraper.py        ← Scraping logic for all 3 portals
├── matcher.py        ← Keyword matching engine
├── database.py       ← SQLite operations (seen tenders, logs)
├── emailer.py        ← HTML email formatting and sending
├── scheduler.py      ← APScheduler (30 min + 8 AM daily)
├── requirements.txt  ← Python dependencies
├── .env.example      ← Environment variable template
├── .env              ← Your credentials (DO NOT commit to Git)
├── gem_tenders.db    ← SQLite database (auto-created)
└── scraper.log       ← Activity log (auto-created)
```

---

## Setup Instructions

### Step 1 — Install Python 3.10+

Download from https://python.org if not already installed.

```bash
python --version   # should show 3.10 or higher
```

### Step 2 — Install Dependencies

```bash
cd gem_alert_system
pip install -r requirements.txt
```

### Step 3 — Set Up Gmail App Password

This system uses Gmail SMTP to send emails. You need a **Gmail App Password** (not your regular Gmail password).

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** (required)
3. Go to **Security → App passwords**
4. Click **Select app → Mail**
5. Click **Select device → Other** → type "GeM Alert"
6. Click **Generate** → copy the 16-character password shown

> Keep this password safe — it only appears once.

### Step 4 — Configure .env File

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in:

```env
TO_EMAIL=madan78au@hotmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx    ← Gmail App Password (16 chars)
FROM_EMAIL=your_gmail@gmail.com
DB_PATH=gem_tenders.db
```

### Step 5 — Run the System

```bash
python main.py
```

You will see logs like:
```
2026-04-12 10:00:00 [INFO] Starting scheduler...
2026-04-12 10:00:00 [INFO] Running initial scrape cycle...
2026-04-12 10:00:05 [INFO] Total tenders fetched: 47
2026-04-12 10:00:05 [INFO] Keyword-matched tenders: 3
2026-04-12 10:00:05 [INFO] NEW tender found: GEM/2026/B/7426028
2026-04-12 10:00:06 [INFO] Alert sent for: GEM/2026/B/7426028
```

The system runs continuously. Press **Ctrl+C** to stop.

---

## Deploy 24/7 for Free (No laptop needed)

### Option A — Railway.app (Recommended, Free)

1. Create a free account at https://railway.app
2. Click **New Project → Deploy from GitHub repo**
3. Push your code to GitHub first:
   ```bash
   git init
   git add .
   git commit -m "GeM alert system"
   git remote add origin https://github.com/YOUR_USERNAME/gem-alert
   git push -u origin main
   ```
   > **Important:** Add `.env` to `.gitignore` so credentials are not exposed.
4. In Railway dashboard → **Variables** tab → add all your `.env` values manually
5. Railway auto-detects Python and runs `python main.py`
6. Done — it runs 24/7 for free

### Option B — Render.com (Free tier)

1. Create account at https://render.com
2. Click **New → Background Worker**
3. Connect your GitHub repo
4. Set **Build Command:** `pip install -r requirements.txt`
5. Set **Start Command:** `python main.py`
6. Add environment variables in the **Environment** tab
7. Deploy — runs 24/7

### Option C — Run on your PC overnight

Just run `python main.py` and leave it running. Works fine if your PC stays on.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "SMTP authentication failed" | Check Gmail App Password in .env (not your regular password) |
| "Could not fetch bidplus.gem.gov.in" | GeM portal may be temporarily down — system retries automatically |
| No tenders being found | GeM may have changed their HTML structure — check scraper.log |
| Emails going to spam | Add your Gmail address to madan78au@hotmail.com contacts |
| "chromedriver not found" | Install Chrome browser and run: `pip install webdriver-manager` |

---

## Logs

All activity is logged to `scraper.log`:
```
2026-04-12 10:30:00 [INFO] Scrape cycle started
2026-04-12 10:30:03 [INFO] bidplus.gem.gov.in: 42 tenders
2026-04-12 10:30:05 [INFO] NEW tender: GEM/2026/B/7430000
2026-04-12 10:30:06 [INFO] Alert sent ✓
```

---

## Security Notes

- Never commit `.env` to GitHub
- Add `.env` to your `.gitignore` file
- Gmail App Passwords can be revoked anytime from your Google account
- The SQLite database (`gem_tenders.db`) stores only bid numbers and titles — no personal data

---

## Support

If the GeM portal structure changes and scraping breaks, open `scraper.py` and update the CSS selectors in the `parse_bidplus_card()` function to match the new HTML structure.
