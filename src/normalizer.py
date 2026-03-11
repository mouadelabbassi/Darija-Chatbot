from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import re

from .merge_detector import auto_fix_boundary_merges, detect_merge_candidates
from .script_detector import script_profile

INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]")
MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
MULTI_BREAK_RE = re.compile(r"\r\n?|\n")
REPEATED_PUNCT_RE = re.compile(r"([!?؟.,،;:])\1{1,}")
TATWEEL_RE = re.compile(r"ـ+")
PUNCT_SPACING_RE = re.compile(r"\s*([,،;:!?؟\.])\s*")


@dataclass
class TextNormalizationResult:
    cleaned: str
    changed: bool
    applied_rules: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    script: dict[str, float | str] = field(default_factory=dict)


class DarijaNormalizer:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def _apply_arabic_variant_map(self, text: str) -> tuple[str, bool]:
        mapping = self.cfg.get("arabic_variant_map", {})
        changed = False
        for src, dst in mapping.items():
            if src in text:
                text = text.replace(src, dst)
                changed = True
        return text, changed

    def normalize_text(self, text: str) -> TextNormalizationResult:
        original = text or ""
        rules: list[str] = []
        issues: list[dict] = []
        text = original

        text = unicodedata.normalize(self.cfg.get("unicode_form", "NFKC"), text)

        if self.cfg.get("remove_invisible_chars", True):
            new_text = INVISIBLE_RE.sub("", text)
            if new_text != text:
                text = new_text
                rules.append("remove_invisible_chars")

        if self.cfg.get("remove_tatweel", True):
            new_text = TATWEEL_RE.sub("", text)
            if new_text != text:
                text = new_text
                rules.append("remove_tatweel")

        if self.cfg.get("normalize_line_breaks", True):
            new_text = MULTI_BREAK_RE.sub("\n", text)
            if new_text != text:
                text = new_text
                rules.append("normalize_line_breaks")

        if self.cfg.get("strip_text", True):
            new_text = text.strip()
            if new_text != text:
                text = new_text
                rules.append("strip")

        if self.cfg.get("collapse_spaces", True):
            new_text = MULTI_SPACE_RE.sub(" ", text)
            if new_text != text:
                text = new_text
                rules.append("collapse_spaces")

        if self.cfg.get("normalize_quotes", True):
            quote_map = {"“": '"', "”": '"', "’": "'", "‘": "'"}
            for src, dst in quote_map.items():
                text = text.replace(src, dst)
            rules.append("normalize_quotes")

        if self.cfg.get("normalize_repeated_punctuation", True):
            new_text = REPEATED_PUNCT_RE.sub(r"\1", text)
            if new_text != text:
                text = new_text
                rules.append("normalize_repeated_punctuation")

        if self.cfg.get("normalize_punctuation_spacing", True):
            new_text = PUNCT_SPACING_RE.sub(r"\1 ", text)
            new_text = MULTI_SPACE_RE.sub(" ", new_text).strip()
            if new_text != text:
                text = new_text
                rules.append("normalize_punctuation_spacing")

        if self.cfg.get("normalize_arabic_variants", False):
            new_text, changed = self._apply_arabic_variant_map(text)
            if changed:
                text = new_text
                rules.append("normalize_arabic_variants")

        merge_meta = detect_merge_candidates(text)
        if self.cfg.get("boundary_merge_enabled", True) and merge_meta["boundary_merges"]:
            if self.cfg.get("boundary_merge_auto_fix", True):
                fixed = auto_fix_boundary_merges(text)
                if fixed != text:
                    text = fixed
                    rules.append("boundary_merge_auto_fix")
            issues.append(
                {
                    "issue_type": "possible_boundary_merge",
                    "confidence": merge_meta["confidence"],
                    "details": merge_meta,
                }
            )

        return TextNormalizationResult(
            cleaned=text,
            changed=(text != original),
            applied_rules=rules,
            issues=issues,
            script=script_profile(text),
        )
