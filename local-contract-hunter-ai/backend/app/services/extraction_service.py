from __future__ import annotations

import re
from datetime import datetime


DATE_PATTERNS = [
    r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
    r"\b([A-Za-z]+\s+\d{1,2},\s+\d{4})\b",
]


def parse_possible_due_date(text: str):
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1)
        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def snippet_with_keywords(text: str, keywords: list[str]) -> str:
    lowered = text.lower()
    for keyword in keywords:
        idx = lowered.find(keyword.lower())
        if idx >= 0:
            start = max(0, idx - 120)
            end = min(len(text), idx + 240)
            return text[start:end].strip()
    return text[:300].strip()


def confidence_from_text(text: str, keywords: list[str]) -> float:
    if not text:
        return 0.1
    hits = sum(1 for keyword in keywords if keyword.lower() in text.lower())
    if hits >= 4:
        return 0.9
    if hits >= 2:
        return 0.75
    if hits == 1:
        return 0.6
    return 0.35
