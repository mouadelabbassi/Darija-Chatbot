from __future__ import annotations

import argparse
from pathlib import Path


from src.deduper import exact_deduplicate, near_duplicate_candidates
from src.flagger import FlaggedCase, flag_rows
from src.io_utils import backup_raw_payload, load_records
from src.normalizer import DarijaNormalizer
from src.reporting import build_quality_report, write_reports
from src.reviewer import run_terminal_review, write_flagged_outputs, write_review_summary
from src.utils import ensure_directories, load_config, setup_logger, write_json


def run_pipeline(config_path: Path) -> None:
    cfg = load_config(config_path)
    logger = setup_logger(Path(cfg["log_path"]))

    ensure_directories(
        [
            Path("data/raw"),
            Path("data/processed"),
            Path("data/review"),
            Path("data/reports"),
            Path("logs"),
        ]
    )

    input_path = Path(cfg["input_path"])
    version = cfg["output_version"]

    payload, qa_rows = load_records(input_path)
    logger.info("Loaded %s rows from %s", len(qa_rows), input_path)

    if cfg.get("aio", {}).get("preserve_raw_backup", True):
        backup_raw_payload(payload, Path("data/raw/raw_backup.json"))

    normalizer = DarijaNormalizer({**cfg["normalization"], **cfg["merge_detection"]})
    processed: list[dict] = []
    sample_changes: list[dict] = []

    for row in qa_rows:
        qn = normalizer.normalize_text(row.question)
        an = normalizer.normalize_text(row.answer)
        changed = qn.changed or an.changed
        packed = {
            "row_id": row.row_id,
            "context_id": row.context_id,
            "question": row.question,
            "answer": row.answer,
            "cleaned_question": qn.cleaned,
            "cleaned_answer": an.cleaned,
            "changed": changed,
            "applied_rules": sorted(set(qn.applied_rules + an.applied_rules)),
            "normalization_issues": qn.issues + an.issues,
            "script_profile": {
                "label": "mixed" if qn.script["label"] != an.script["label"] else qn.script["label"],
                "arabic_ratio": round((qn.script["arabic_ratio"] + an.script["arabic_ratio"]) / 2, 3),
                "latin_ratio": round((qn.script["latin_ratio"] + an.script["latin_ratio"]) / 2, 3),
            },
        }
        if changed and len(sample_changes) < cfg["reporting"]["sample_changes"]:
            sample_changes.append(
                {
                    "row_id": row.row_id,
                    "question_before": row.question,
                    "question_after": qn.cleaned,
                    "answer_before": row.answer,
                    "answer_after": an.cleaned,
                }
            )
        processed.append(packed)

    clean_path = Path(f"data/processed/clean_{version}.json")
    write_json(clean_path, processed)
    logger.info("Wrote normalized dataset to %s", clean_path)

    rows_removed = 0
    exact_count = 0
    if cfg["exact_dedup"]["enabled"]:
        exact_result = exact_deduplicate(processed, cfg["exact_dedup"]["mode"])
        exact_count = len(exact_result.duplicate_row_ids)
        processed = [row for row in processed if row["row_id"] not in exact_result.duplicate_row_ids]
        rows_removed += exact_count
        logger.info("Exact dedup removed %s rows", exact_count)

    near_candidates = []
    if cfg["near_dedup"]["enabled"]:
        near_candidates = near_duplicate_candidates(processed, cfg["near_dedup"])
        logger.info("Detected %s near-duplicate candidates", len(near_candidates))

        if cfg["near_dedup"].get("auto_remove_high_confidence", False):
            remove_ids = {c.row_id_2 for c in near_candidates if c.confidence == "high"}
            processed = [row for row in processed if row["row_id"] not in remove_ids]
            rows_removed += len(remove_ids)
            logger.info("Auto-removed %s high-confidence near duplicates", len(remove_ids))

    dedup_path = Path(f"data/processed/deduped_{version}.json")
    write_json(dedup_path, processed)

    flagged: list[FlaggedCase] = flag_rows(processed, cfg["flagging"])
    for cand in near_candidates:
        if cand.confidence == "medium":
            row = next((r for r in processed if r["row_id"] == cand.row_id_1), None)
            if row:
                flagged.append(
                    FlaggedCase(
                        row_id=row["row_id"],
                        context_id=row["context_id"],
                        original_question=row["question"],
                        cleaned_question=row["cleaned_question"],
                        original_answer=row["answer"],
                        cleaned_answer=row["cleaned_answer"],
                        issue_type="near_duplicate_medium",
                        confidence_score=0.85,
                        recommended_action=f"compare_with_row_{cand.row_id_2}",
                        notes=f"rf={cand.rapidfuzz_score:.1f}, jac={cand.token_jaccard:.2f}, cos={cand.tfidf_cosine:.2f}",
                    )
                )

    if cfg["review"]["write_review_files"]:
        write_flagged_outputs(flagged, Path("data/review/flagged_cases.csv"), Path("data/review/flagged_cases.jsonl"))
        write_review_summary(flagged, Path("data/review/review_summary.md"))

    report = build_quality_report(
        rows=processed,
        flagged_cases=[f.__dict__ for f in flagged],
        exact_duplicate_count=exact_count,
        near_candidates_count=len(near_candidates),
        rows_removed=rows_removed,
        sample_changes=sample_changes,
    )
    write_reports(report, Path("data/reports/quality_report.json"), Path("data/reports/quality_report.md"))
    logger.info("Pipeline finished successfully")


def main() -> None:
    parser = argparse.ArgumentParser(description="Darija Q/A cleaning and review pipeline")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to YAML config")
    parser.add_argument("--review", action="store_true", help="Launch terminal reviewer on flagged cases")
    args = parser.parse_args()

    if args.review:
        cfg = load_config(args.config)
        run_terminal_review(Path("data/review/flagged_cases.jsonl"), Path(cfg["review"]["decisions_file"]))
        return

    run_pipeline(args.config)


if __name__ == "__main__":
    main()
