"""
matcher.py — Keyword Matching Engine
Matches tenders against the defined keyword list (case-insensitive, partial match).
"""

import re
from typing import List, Dict, Tuple

# ── Master keyword list ───────────────────────────────────────────────────────
KEYWORDS = [
    # Primary
    "e-learning",
    "elearning",
    "content development",
    "content design",
    "content designing",
    "storyboarding",
    "storyboard",
    "interactive content creation",
    "interactive content",
    # Technology
    "ar/vr",
    "ar vr",
    "augmented reality",
    "virtual reality",
    "immersive learning",
    "immersive solutions",
    "immersive technology",
    "xr application",
    "mixed reality",
    # Platform
    "igot",
    "i-got",
    "integrated government online training",
    "karmayogi",
    # Level-based
    "level-1",
    "level 1",
    "level-2",
    "level 2",
    "level-3",
    "level 3",
    # Additional variations
    "lms content",
    "scorm",
    "multimedia content",
    "instructional design",
    "e learning content",
]

# Compile all patterns once for performance
_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in KEYWORDS]


def match_keywords(tender: Dict) -> Tuple[bool, List[str]]:
    """
    Check if a tender matches any keyword.
    Returns (is_match: bool, matched_keywords: List[str])
    """
    # Build the text to search — title + description combined
    search_text = " ".join([
        tender.get("title", ""),
        tender.get("description", ""),
        tender.get("organisation", ""),
        tender.get("bid_no", ""),
    ]).lower()

    matched = []
    for kw, pattern in zip(KEYWORDS, _PATTERNS):
        if pattern.search(search_text):
            matched.append(kw)

    # Deduplicate while preserving order
    seen = set()
    unique_matched = []
    for kw in matched:
        if kw not in seen:
            seen.add(kw)
            unique_matched.append(kw)

    return len(unique_matched) > 0, unique_matched


def filter_tenders(tenders: List[Dict]) -> List[Dict]:
    """
    Filter a list of tenders and return only those matching keywords.
    Adds 'matched_keywords' field to each matching tender.
    """
    matched_tenders = []

    for tender in tenders:
        is_match, matched_kws = match_keywords(tender)
        if is_match:
            tender["matched_keywords"] = matched_kws
            matched_tenders.append(tender)

    return matched_tenders


def highlight_keywords(text: str, keywords: List[str]) -> str:
    """
    Return HTML with matched keywords highlighted in yellow.
    Used for email formatting.
    """
    for kw in keywords:
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        text = pattern.sub(
            lambda m: f'<mark style="background:#fff3cd;padding:1px 3px;border-radius:3px;">{m.group(0)}</mark>',
            text,
        )
    return text
