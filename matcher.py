"""
matcher.py — Keyword matching engine
Checks tender titles/descriptions against the keyword list.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# PRIMARY KEYWORDS (high-priority match)
# ─────────────────────────────────────────────
PRIMARY_KEYWORDS = [
    # iGOT / Karmayogi
    "igot", "iGOT", "karmayogi", "integrated government online training",
    # E-Learning
    "e-learning", "elearning", "e learning", "online learning",
    "digital learning", "digital content",
    # Content Development
    "content development", "content design", "content creation",
    "storyboarding", "instructional design", "courseware",
    "multimedia content", "learning content",
    # LMS
    "lms", "learning management system", "learning management",
    # AR / VR / Immersive
    "ar/vr", "ar vr", "augmented reality", "virtual reality",
    "immersive learning", "immersive technology", "vr training",
    "mixed reality", "xr", "extended reality", "simulation based",
    # DLS / Novac products
    "digital learning solutions", "dls",
    # Other relevant
    "online training", "blended learning", "gamification",
    "mobile learning", "mlearning", "scorm", "tin can", "xapi",
    "rapid authoring", "animation training", "2d animation",
    "3d animation", "explainer video",
]

# ─────────────────────────────────────────────
# SECONDARY KEYWORDS (context boosters)
# ─────────────────────────────────────────────
SECONDARY_KEYWORDS = [
    "training", "skilling", "capacity building", "skill development",
    "nsdc", "nielit", "dopt", "ministry", "government training",
    "cpd", "professional development", "upskilling",
]

# ─────────────────────────────────────────────
# EXCLUSION TERMS (reduce false positives)
# ─────────────────────────────────────────────
EXCLUDE_TERMS = [
    "hand pump", "solar panel", "fodder", "road construction",
    "civil works", "plumbing", "electrical wiring", "furniture supply",
    "vehicle", "generator", "pump", "valve",
]


def normalize(text):
    return text.lower().strip()


def match_tender(tender, extra_keywords=None):
    """
    Returns (matched: bool, score: int, matched_keywords: list)
    Score = number of keyword hits. Higher = more relevant.
    """
    title = normalize(tender.get("title", ""))

    # Hard exclude
    for excl in EXCLUDE_TERMS:
        if excl.lower() in title:
            return False, 0, []

    all_primary = list(PRIMARY_KEYWORDS)
    if extra_keywords:
        all_primary.extend([k.lower() for k in extra_keywords])

    matched_kws = []
    score = 0

    for kw in all_primary:
        pattern = re.compile(re.escape(kw.lower()), re.IGNORECASE)
        if pattern.search(title):
            matched_kws.append(kw)
            score += 2  # primary keyword = 2 points

    for kw in SECONDARY_KEYWORDS:
        if kw.lower() in title:
            score += 1  # secondary = 1 point

    matched = score >= 2  # at least 1 primary keyword hit
    return matched, score, matched_kws


def filter_tenders(tenders, extra_keywords=None):
    """Filter and rank tenders by relevance score."""
    matched = []
    for t in tenders:
        is_match, score, kws = match_tender(t, extra_keywords)
        if is_match:
            t["score"] = score
            t["matched_keywords"] = kws
            matched.append(t)

    # Sort by score descending
    matched.sort(key=lambda x: x.get("score", 0), reverse=True)
    logger.info(f"Matched {len(matched)} relevant tenders out of {len(tenders)} total")
    return matched
