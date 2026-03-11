from __future__ import annotations

import re

AR = r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]"
LA = r"[A-Za-zÀ-ÖØ-öø-ÿ]"

AR_LAT_BOUNDARY = re.compile(rf"(?P<a>{AR})(?P<b>{LA})")
LAT_AR_BOUNDARY = re.compile(rf"(?P<a>{LA})(?P<b>{AR})")
AR_PUNCT_BOUNDARY = re.compile(rf"({AR}|{LA})([,،;:!?؟])({AR}|{LA})")


def detect_merge_candidates(text: str) -> dict:
    ar_lat = len(AR_LAT_BOUNDARY.findall(text))
    lat_ar = len(LAT_AR_BOUNDARY.findall(text))
    punct_merge = len(AR_PUNCT_BOUNDARY.findall(text))

    total = ar_lat + lat_ar + punct_merge
    confidence = 0.95 if total > 0 else 1.0
    return {
        "boundary_merges": total,
        "ar_lat": ar_lat,
        "lat_ar": lat_ar,
        "punct_merges": punct_merge,
        "confidence": confidence,
    }


def auto_fix_boundary_merges(text: str) -> str:
    text = AR_LAT_BOUNDARY.sub(r"\g<a> \g<b>", text)
    text = LAT_AR_BOUNDARY.sub(r"\g<a> \g<b>", text)
    text = AR_PUNCT_BOUNDARY.sub(r"\1\2 \3", text)
    return text
