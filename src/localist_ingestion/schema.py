from __future__ import annotations

from pathlib import Path
import json


def load_columns(repo_root: Path, schema_name: str = "review_queue_columns.json") -> list[str]:
    schema_path = repo_root / "schemas" / schema_name
    with schema_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return list(raw["columns"])


def load_review_queue_columns(repo_root: Path) -> list[str]:
    return load_columns(repo_root, "review_queue_columns.json")


def column_letter(column_number: int) -> str:
    result = ""
    while column_number > 0:
        column_number, remainder = divmod(column_number - 1, 26)
        result = chr(65 + remainder) + result
    return result
