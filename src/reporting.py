from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from .utils import write_json


def _dist(values: list[int]) -> dict[str, float]:
    if not values:
        return {"min": 0, "max": 0, "avg": 0.0}
    return {"min": min(values), "max": max(values), "avg": round(mean(values), 2)}


def build_quality_report(
    rows: list[dict],
    flagged_cases: list[dict],
    exact_duplicate_count: int,
    near_candidates_count: int,
    rows_removed: int,
    sample_changes: list[dict],
) -> dict[str, Any]:
    total = len(rows)
    missing_fields = sum(1 for r in rows if not r["question"].strip() or not r["answer"].strip())
    modified = sum(1 for r in rows if r["changed"])

    script_counts = Counter(r["script_profile"]["label"] for r in rows)
    issue_counts = Counter(c["issue_type"] for c in flagged_cases)

    q_lengths = [len(r["cleaned_question"]) for r in rows]
    a_lengths = [len(r["cleaned_answer"]) for r in rows]

    whitespace_noise = sum(1 for r in rows if "  " in r["question"] or "  " in r["answer"])
    punct_noise = sum(1 for r in rows if any(ch * 2 in r["question"] + r["answer"] for ch in "!?؟.,،;:"))
    merge_issue_count = sum(
        1
        for r in rows
        for issue in r.get("normalization_issues", [])
        if issue.get("issue_type") == "possible_boundary_merge"
    )

    return {
        "total_rows": total,
        "rows_with_missing_fields": missing_fields,
        "rows_modified_by_normalization": modified,
        "rows_auto_fixed": modified,
        "rows_flagged_for_review": len(flagged_cases),
        "exact_duplicates_found": exact_duplicate_count,
        "near_duplicate_candidates_found": near_candidates_count,
        "rows_removed": rows_removed,
        "script_type_counts": dict(script_counts),
        "punctuation_noise_rows": punct_noise,
        "whitespace_noise_rows": whitespace_noise,
        "estimated_merged_word_issue_count": merge_issue_count,
        "question_length_distribution": _dist(q_lengths),
        "answer_length_distribution": _dist(a_lengths),
        "top_issue_categories": dict(issue_counts.most_common(10)),
        "sample_before_after": sample_changes,
    }


def write_reports(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    write_json(json_path, report)

    lines = [
        "# Darija Data Quality Report",
        "",
        "## Summary",
        f"- Total rows: **{report['total_rows']}**",
        f"- Rows modified by normalization: **{report['rows_modified_by_normalization']}**",
        f"- Rows flagged for manual review: **{report['rows_flagged_for_review']}**",
        f"- Exact duplicates found: **{report['exact_duplicates_found']}**",
        f"- Near-duplicate candidates: **{report['near_duplicate_candidates_found']}**",
        f"- Rows removed: **{report['rows_removed']}**",
        "",
        "## Script Distribution",
    ]
    for k, v in report["script_type_counts"].items():
        lines.append(f"- {k}: {v}")

    lines.extend([
        "",
        "## Conservative Policy",
        "- Low-confidence corrections are flagged instead of auto-applied.",
        "- Mixed-script and noisy rows are preserved with review recommendations.",
        "- Original text is retained for auditing in processed outputs.",
        "",
        "## Sample Before/After",
    ])

    for sample in report["sample_before_after"]:
        lines.extend([
            "",
            f"- row_id `{sample['row_id']}`",
            f"  - question_before: {sample['question_before']}",
            f"  - question_after : {sample['question_after']}",
            f"  - answer_before  : {sample['answer_before'][:200]}",
            f"  - answer_after   : {sample['answer_after'][:200]}",
        ])

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
