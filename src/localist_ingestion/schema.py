from __future__ import annotations

from pathlib import Path
import json


def load_review_queue_columns(repo_root: Path) -> list[str]:
    schema_path = repo_root / "schemas" / "review_queue_columns.json"
    with schema_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return list(raw["columns"])

