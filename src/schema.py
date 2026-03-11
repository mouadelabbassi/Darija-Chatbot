from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class QARecord:
    row_id: int
    context_id: str
    question: str
    answer: str
    raw: dict[str, Any]


def _flatten_records(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(payload, dict):
        # Prioritize obvious list containers.
        for candidate_key in ["data", "records", "items", "dataset", "rows"]:
            candidate = payload.get(candidate_key)
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, dict):
                        yield item
                return

        # fallback: recursive search for first sizable list of dicts
        for value in payload.values():
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                for item in value:
                    yield item
                return


FIELD_CANDIDATES = {
    "context_id": ["context_id", "context", "topic", "id"],
    "question": ["question", "q", "prompt", "input"],
    "answer": ["answer", "a", "response", "output"],
}


def _pick_field(record: dict[str, Any], logical_name: str) -> str | None:
    for key in FIELD_CANDIDATES[logical_name]:
        if key in record:
            return key
    return None


def detect_schema(records: list[dict[str, Any]]) -> dict[str, str]:
    if not records:
        raise ValueError("No records detected in JSON payload.")

    sample = records[0]
    mapping = {}
    for logical_name in ["context_id", "question", "answer"]:
        selected = _pick_field(sample, logical_name)
        if selected is None and logical_name != "context_id":
            raise ValueError(f"Unable to detect required field: {logical_name}")
        if selected:
            mapping[logical_name] = selected

    mapping.setdefault("context_id", "context_id")
    return mapping


def to_qa_records(payload: Any) -> list[QARecord]:
    raw_records = list(_flatten_records(payload))
    schema = detect_schema(raw_records)

    rows: list[QARecord] = []
    for idx, record in enumerate(raw_records):
        q = str(record.get(schema["question"], "") or "")
        a = str(record.get(schema["answer"], "") or "")
        c = str(record.get(schema.get("context_id", "context_id"), "") or "")
        rows.append(QARecord(row_id=idx, context_id=c, question=q, answer=a, raw=record))
    return rows
