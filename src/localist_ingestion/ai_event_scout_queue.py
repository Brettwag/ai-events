from __future__ import annotations

import json
from pathlib import Path

from .models import RuntimeConfig
from .review_queue import GoogleSheetsReviewQueue
from .event_scout import AIEventScoutCandidate


class GoogleSheetsAIEventScoutQueue(GoogleSheetsReviewQueue):
    def __init__(self, runtime: RuntimeConfig, repo_root: Path) -> None:
        super().__init__(runtime=runtime, repo_root=repo_root)
        self.sheet_name = runtime.ai_event_scout_sheet_name
        self.columns = self._load_columns(repo_root)

    @staticmethod
    def _load_columns(repo_root: Path) -> list[str]:
        schema_path = repo_root / "schemas" / "ai_event_scout_columns.json"
        with schema_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return list(raw["columns"])

    def upsert_candidates(self, candidates: list[AIEventScoutCandidate], run_date: str) -> dict[str, int]:
        self.ensure_sheet_ready()
        existing = self._existing_rows()
        updates = 0
        inserts = 0
        append_rows: list[list[str]] = []

        for candidate in candidates:
            row_values = self._record_to_row(
                self._merge_existing_state(candidate.to_sheet_record(run_date), existing.get(candidate.scout_event_id))
            )
            existing_row_number = existing.get(candidate.scout_event_id, {}).get("row_number")
            if existing_row_number:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A{existing_row_number}:W{existing_row_number}",
                    valueInputOption="RAW",
                    body={"values": [row_values]},
                ).execute()
                updates += 1
            else:
                append_rows.append(row_values)
                inserts += 1

        if append_rows:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:W",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": append_rows},
            ).execute()

        return {"updated": updates, "inserted": inserts}

    def _existing_rows(self) -> dict[str, dict]:
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A:W",
        ).execute()
        values = response.get("values", [])
        if len(values) <= 1:
            return {}
        header = values[0]
        rows = values[1:]
        header_index = {name: index for index, name in enumerate(header)}
        event_id_index = header_index.get("scout_event_id")
        if event_id_index is None:
            return {}
        existing: dict[str, dict] = {}
        for offset, row in enumerate(rows, start=2):
            if event_id_index >= len(row):
                continue
            scout_event_id = row[event_id_index].strip()
            if not scout_event_id:
                continue
            existing[scout_event_id] = {
                "row_number": offset,
                "review_decision": self._value_at(row, header_index, "review_decision"),
                "review_notes": self._value_at(row, header_index, "review_notes"),
                "promote_to_main_queue": self._value_at(row, header_index, "promote_to_main_queue"),
            }
        return existing

    @staticmethod
    def _merge_existing_state(record: dict[str, str], existing: dict | None) -> dict[str, str]:
        if not existing:
            return record
        for field in ["review_decision", "review_notes", "promote_to_main_queue"]:
            if existing.get(field):
                record[field] = existing[field]
        return record
