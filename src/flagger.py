from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FlaggedCase:
    row_id: int
    context_id: str
    original_question: str
    cleaned_question: str
    original_answer: str
    cleaned_answer: str
    issue_type: str
    confidence_score: float
    recommended_action: str
    notes: str


def _noise_ratios(text: str) -> tuple[float, float]:
    if not text:
        return 0.0, 0.0
    numeric = sum(ch.isdigit() for ch in text) / len(text)
    symbols = sum((not ch.isalnum() and not ch.isspace()) for ch in text) / len(text)
    return numeric, symbols


def flag_rows(rows: list[dict], cfg: dict) -> list[FlaggedCase]:
    out: list[FlaggedCase] = []
    for row in rows:
        q = row["cleaned_question"]
        a = row["cleaned_answer"]
        profile = row["script_profile"]

        if len(q.strip()) < cfg["min_text_len"] or len(a.strip()) < cfg["min_text_len"]:
            out.append(
                FlaggedCase(
                    row_id=row["row_id"],
                    context_id=row["context_id"],
                    original_question=row["question"],
                    cleaned_question=q,
                    original_answer=row["answer"],
                    cleaned_answer=a,
                    issue_type="empty_or_too_short",
                    confidence_score=0.5,
                    recommended_action="manual_edit",
                    notes="Question or answer is near-empty.",
                )
            )

        if len(q) > cfg["max_question_len"] or len(a) > cfg["max_answer_len"]:
            out.append(
                FlaggedCase(
                    row_id=row["row_id"],
                    context_id=row["context_id"],
                    original_question=row["question"],
                    cleaned_question=q,
                    original_answer=row["answer"],
                    cleaned_answer=a,
                    issue_type="extreme_length",
                    confidence_score=0.7,
                    recommended_action="review_length",
                    notes="Potentially malformed or off-format conversational row.",
                )
            )

        numeric_q, symbol_q = _noise_ratios(q)
        numeric_a, symbol_a = _noise_ratios(a)
        if max(numeric_q, numeric_a) >= cfg["numeric_ratio_warn"]:
            out.append(
                FlaggedCase(
                    row_id=row["row_id"],
                    context_id=row["context_id"],
                    original_question=row["question"],
                    cleaned_question=q,
                    original_answer=row["answer"],
                    cleaned_answer=a,
                    issue_type="numeric_heavy",
                    confidence_score=0.75,
                    recommended_action="fact_check",
                    notes="High digit density; likely fact-heavy content.",
                )
            )

        if max(symbol_q, symbol_a) >= cfg["symbol_ratio_warn"]:
            out.append(
                FlaggedCase(
                    row_id=row["row_id"],
                    context_id=row["context_id"],
                    original_question=row["question"],
                    cleaned_question=q,
                    original_answer=row["answer"],
                    cleaned_answer=a,
                    issue_type="symbol_noise",
                    confidence_score=0.7,
                    recommended_action="manual_review",
                    notes="Unusual symbol density detected.",
                )
            )

        if profile["label"] == "mixed" and min(profile["arabic_ratio"], profile["latin_ratio"]) >= cfg["mixed_script_heavy_threshold"]:
            out.append(
                FlaggedCase(
                    row_id=row["row_id"],
                    context_id=row["context_id"],
                    original_question=row["question"],
                    cleaned_question=q,
                    original_answer=row["answer"],
                    cleaned_answer=a,
                    issue_type="heavy_mixed_script",
                    confidence_score=0.8,
                    recommended_action="review_script_consistency",
                    notes="Arabic/Latin split is heavy and may hide merge/noise issues.",
                )
            )

        for issue in row.get("normalization_issues", []):
            if issue.get("confidence", 1.0) < cfg["low_confidence_threshold"]:
                out.append(
                    FlaggedCase(
                        row_id=row["row_id"],
                        context_id=row["context_id"],
                        original_question=row["question"],
                        cleaned_question=q,
                        original_answer=row["answer"],
                        cleaned_answer=a,
                        issue_type=issue.get("issue_type", "normalization_uncertain"),
                        confidence_score=float(issue.get("confidence", 0.5)),
                        recommended_action="review_auto_fix",
                        notes=str(issue.get("details", {})),
                    )
                )
    return out
