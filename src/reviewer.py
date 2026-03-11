from __future__ import annotations

import csv
import json
from pathlib import Path

from .flagger import FlaggedCase
from .utils import write_jsonl


def write_flagged_outputs(cases: list[FlaggedCase], csv_path: Path, jsonl_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_id",
        "context_id",
        "original_question",
        "cleaned_question",
        "original_answer",
        "cleaned_answer",
        "issue_type",
        "confidence_score",
        "recommended_action",
        "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for case in cases:
            writer.writerow(case.__dict__)

    write_jsonl(jsonl_path, [case.__dict__ for case in cases])


def write_review_summary(cases: list[FlaggedCase], path: Path) -> None:
    by_type: dict[str, int] = {}
    for case in cases:
        by_type[case.issue_type] = by_type.get(case.issue_type, 0) + 1

    lines = ["# Manual Review Summary", "", f"Total flagged cases: **{len(cases)}**", "", "## Issue Breakdown"]
    for issue, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {issue}: {count}")
    lines.extend(
        [
            "",
            "## Guidance",
            "- Approve auto-fix only when meaning is preserved in Darija context.",
            "- Prefer manual edits for mixed Arabic/Arabizi rows with ambiguity.",
            "- Keep original conversational intent over stylistic standardization.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_terminal_review(flagged_jsonl: Path, decisions_output: Path) -> None:
    if not flagged_jsonl.exists():
        raise FileNotFoundError(f"Flagged file not found: {flagged_jsonl}")

    decisions_output.parent.mkdir(parents=True, exist_ok=True)
    decisions: list[dict] = []

    rows = [json.loads(line) for line in flagged_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        print("\n" + "=" * 80)
        print(f"row_id={row['row_id']} | issue={row['issue_type']} | confidence={row['confidence_score']}")
        print(f"Q original: {row['original_question']}")
        print(f"Q cleaned : {row['cleaned_question']}")
        print(f"A original: {row['original_answer'][:200]}")
        print(f"A cleaned : {row['cleaned_answer'][:200]}")
        action = input("Action [approve/reject/edit/duplicate/keep/unsure]: ").strip().lower() or "unsure"

        edit_q = row["cleaned_question"]
        edit_a = row["cleaned_answer"]
        if action == "edit":
            new_q = input("Edited question (empty keeps cleaned): ").strip()
            new_a = input("Edited answer   (empty keeps cleaned): ").strip()
            if new_q:
                edit_q = new_q
            if new_a:
                edit_a = new_a

        decisions.append(
            {
                "row_id": row["row_id"],
                "issue_type": row["issue_type"],
                "decision": action,
                "final_question": edit_q,
                "final_answer": edit_a,
            }
        )

    with decisions_output.open("w", encoding="utf-8") as f:
        for decision in decisions:
            f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    print(f"Saved {len(decisions)} decisions to {decisions_output}")
