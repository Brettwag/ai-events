from __future__ import annotations

from pathlib import Path

from .models import RuntimeConfig
from .review_queue import GoogleSheetsReviewQueue


class GoogleSheetsSourceScoutQueue(GoogleSheetsReviewQueue):
    def __init__(self, runtime: RuntimeConfig, repo_root: Path) -> None:
        super().__init__(runtime=runtime, repo_root=repo_root)
        self.sheet_name = runtime.source_scout_sheet_name
