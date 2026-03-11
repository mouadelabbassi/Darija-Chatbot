from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import QARecord, to_qa_records
from .utils import write_json


def load_json_payload(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_records(path: Path) -> tuple[Any, list[QARecord]]:
    payload = load_json_payload(path)
    rows = to_qa_records(payload)
    return payload, rows


def backup_raw_payload(payload: Any, backup_path: Path) -> None:
    write_json(backup_path, payload)
