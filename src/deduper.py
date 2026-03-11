from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations


@dataclass
class ExactDedupResult:
    duplicate_row_ids: set[int]
    groups: list[list[int]]


@dataclass
class NearDuplicateCandidate:
    row_id_1: int
    row_id_2: int
    rapidfuzz_score: float
    token_jaccard: float
    tfidf_cosine: float
    confidence: str


def _dedup_key(row: dict, mode: str) -> str:
    q = row["cleaned_question"]
    a = row["cleaned_answer"]
    c = row.get("context_id", "")
    if mode == "question_only":
        return q
    if mode == "answer_only":
        return a
    if mode == "question_answer":
        return f"{q}|||{a}"
    return f"{c}|||{q}|||{a}"


def exact_deduplicate(rows: list[dict], mode: str) -> ExactDedupResult:
    buckets: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        buckets[_dedup_key(row, mode)].append(row["row_id"])

    duplicate_ids: set[int] = set()
    groups: list[list[int]] = []
    for ids in buckets.values():
        if len(ids) > 1:
            groups.append(ids)
            duplicate_ids.update(ids[1:])
    return ExactDedupResult(duplicate_row_ids=duplicate_ids, groups=groups)


def _token_jaccard(a: str, b: str) -> float:
    ta = set(a.split())
    tb = set(b.split())
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / max(1, len(ta | tb))


def _char_ngram_vector(text: str, n: int = 3) -> Counter[str]:
    text = f"  {text.lower()}  "
    grams = [text[i : i + n] for i in range(max(0, len(text) - n + 1))]
    return Counter(grams)


def _cosine(counter_a: Counter[str], counter_b: Counter[str]) -> float:
    if not counter_a or not counter_b:
        return 0.0
    shared = set(counter_a) & set(counter_b)
    dot = sum(counter_a[g] * counter_b[g] for g in shared)
    norm_a = sum(v * v for v in counter_a.values()) ** 0.5
    norm_b = sum(v * v for v in counter_b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _block_key(text: str) -> tuple[str, int]:
    compact = re.sub(r"\s+", " ", text.lower()).strip()
    prefix = compact[:48]
    length_bucket = len(compact) // 40
    return prefix, length_bucket


def near_duplicate_candidates(rows: list[dict], cfg: dict) -> list[NearDuplicateCandidate]:
    texts = [f"{r['cleaned_question']} || {r['cleaned_answer']}" for r in rows]
    ids = [r["row_id"] for r in rows]
    vectors = [_char_ngram_vector(t, n=3) for t in texts]

    blocks: dict[tuple[str, int], list[int]] = defaultdict(list)
    for idx, text in enumerate(texts):
        blocks[_block_key(text)].append(idx)

    out: list[NearDuplicateCandidate] = []
    for members in blocks.values():
        if len(members) < 2:
            continue
        for i, j in combinations(members, 2):
            rf = SequenceMatcher(None, texts[i], texts[j]).ratio() * 100
            jac = _token_jaccard(texts[i], texts[j])
            cos = _cosine(vectors[i], vectors[j])

            conf = None
            if rf >= cfg["rapidfuzz_threshold_high"]:
                conf = "high"
            elif (
                rf >= cfg["rapidfuzz_threshold_medium"]
                and jac >= cfg["token_jaccard_threshold_medium"]
                and cos >= cfg["tfidf_cosine_threshold_medium"]
            ):
                conf = "medium"

            if conf:
                out.append(
                    NearDuplicateCandidate(
                        row_id_1=ids[i],
                        row_id_2=ids[j],
                        rapidfuzz_score=rf,
                        token_jaccard=jac,
                        tfidf_cosine=cos,
                        confidence=conf,
                    )
                )
    return out
