"""
matcher.py — Keyword Matching Engine
"""
import re
from typing import List, Dict, Tuple

KEYWORDS = [
    "e-learning", "elearning", "e learning",
    "content development", "content design", "content designing",
    "storyboarding", "storyboard",
    "interactive content creation", "interactive content",
    "ar/vr", "ar vr", "augmented reality", "virtual reality",
    "immersive learning", "immersive solutions", "immersive technology",
    "igot", "i-got", "integrated government online training", "karmayogi",
    "level-1", "level-2", "level-3", "level 1", "level 2", "level 3",
    "lms content", "scorm", "instructional design",
]

_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in KEYWORDS]


def match_keywords(tender: Dict) -> Tuple[bool, List[str]]:
    search_text = " ".join([
        tender.get("title", ""),
        tender.get("description", ""),
        tender.get("organisation", ""),
        tender.get("bid_no", ""),
    ])
    matched = []
    for kw, pattern in zip(KEYWORDS, _PATTERNS):
        if pattern.search(search_text):
            matched.append(kw)
    seen = set()
    unique = []
    for kw in matched:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return len(unique) > 0, unique


def filter_tenders(tenders: List[Dict]) -> List[Dict]:
    matched = []
    for t in tenders:
        is_match, kws = match_keywords(t)
        if is_match:
            t["matched_keywords"] = kws
            matched.append(t)
    return matched


def highlight_keywords(text: str, keywords: List[str]) -> str:
    for kw in keywords:
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        text = pattern.sub(
            lambda m: f'<mark style="background:#fff3cd;padding:1px 3px;border-radius:3px;">{m.group(0)}</mark>',
            text,
        )
    return text
