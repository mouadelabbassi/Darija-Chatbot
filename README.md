# Darija-Chatbot Data Cleaning Pipeline

Production-oriented, conservative pipeline for cleaning Moroccan Darija Q/A JSON data with auditability, deduplication, and manual review.

## Why this is Darija-specific
This project explicitly handles:
- Arabic script Darija
- Arabizi / Latin Darija
- Mixed Arabic + Latin + French/English code-switching
- Script-boundary merges (`ArabicWordLatinWord` and inverse)
- Conservative normalization to preserve dialect meaning

## Real dataset structure (inspected)
`Master_QA_Dataset.json` is a **list of 6,293 objects** with:
- `context_id`
- `question`
- `answer`

The pipeline still supports adaptive parsing for other JSON envelope styles (list, dict with nested list).

## Project tree

```text
.
├── README.md
├── requirements.txt
├── config.yaml
├── main.py
├── Master_QA_Dataset.json
├── src/
│   ├── __init__.py
│   ├── io_utils.py
│   ├── schema.py
│   ├── normalizer.py
│   ├── script_detector.py
│   ├── merge_detector.py
│   ├── deduper.py
│   ├── flagger.py
│   ├── reviewer.py
│   ├── reporting.py
│   └── utils.py
├── data/
│   ├── raw/
│   ├── processed/
│   ├── review/
│   └── reports/
└── logs/
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run pipeline

```bash
python main.py --config config.yaml
```

## Run manual review CLI

```bash
python main.py --config config.yaml --review
```

This terminal reviewer supports:
- approve auto-fix
- reject auto-fix
- edit cleaned text manually
- mark duplicate / keep / unsure
- export decisions to JSONL

## Outputs
After a run, you get:
- `data/raw/raw_backup.json`
- `data/processed/clean_v1.json`
- `data/processed/deduped_v1.json`
- `data/review/flagged_cases.csv`
- `data/review/flagged_cases.jsonl`
- `data/review/review_summary.md`
- `data/reports/quality_report.json`
- `data/reports/quality_report.md`
- `logs/pipeline.log`

## Conservative design principles
- Never overwrite original dataset.
- Keep original and cleaned text in processed rows.
- Low-confidence fixes are **flagged**, not auto-applied.
- Near-duplicates at medium confidence are sent to review.
- All transformations remain auditable via rule traces and before/after examples.

## Configuration highlights (`config.yaml`)
Tune safely:
- normalization strictness
- Arabic variant normalization toggle
- punctuation and spacing behavior
- exact dedup mode
- near-duplicate thresholds
- flagging thresholds
- optional auto-remove for very high-confidence near duplicates
- output version naming

## Notes on maintainability
- Python 3.11+
- Typed, modular code
- Deterministic pipeline runs
- Defensive JSON/schema handling
- Structured logging
