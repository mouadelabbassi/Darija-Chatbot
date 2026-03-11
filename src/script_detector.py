from __future__ import annotations

import re

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def script_profile(text: str) -> dict[str, float | str]:
    text = text or ""
    arabic_chars = len(ARABIC_RE.findall(text))
    latin_chars = len(LATIN_RE.findall(text))
    alpha_chars = arabic_chars + latin_chars

    if alpha_chars == 0:
        label = "unknown"
    elif arabic_chars > 0 and latin_chars == 0:
        label = "arabic"
    elif latin_chars > 0 and arabic_chars == 0:
        label = "latin"
    else:
        label = "mixed"

    return {
        "label": label,
        "arabic_ratio": arabic_chars / alpha_chars if alpha_chars else 0.0,
        "latin_ratio": latin_chars / alpha_chars if alpha_chars else 0.0,
    }
