from __future__ import annotations

from pathlib import Path

from .models import RuntimeConfig
from .review_queue import GoogleSheetsReviewQueue
from .source_scout import SourceScoutCandidate


class GoogleSheetsSourceScoutQueue(GoogleSheetsReviewQueue):
    def __init__(self, runtime: RuntimeConfig, repo_root: Path) -> None:
        super().__init__(runtime=runtime, repo_root=repo_root)
        self.sheet_name = runtime.source_scout_sheet_name
        self.columns = self._load_source_scout_columns(repo_root)

    @staticmethod
    def _load_source_scout_columns(repo_root: Path) -> list[str]:
        from .schema import load_review_queue_columns
        import json

        schema_path = repo_root / "schemas" / "source_scout_columns.json"
        with schema_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return list(raw["columns"])

    def upsert_candidates(self, candidates: list[SourceScoutCandidate], run_date: str) -> dict[str, int]:
        self.ensure_sheet_ready()
        existing = self._existing_rows_by_candidate_id()
        updates = 0
        inserts = 0
        append_rows: list[list[str]] = []

        for candidate in candidates:
            row_values = self._record_to_row(
                self._merge_existing_state(candidate.to_sheet_record(run_date), existing.get(candidate.candidate_id))
            )
            existing_row_number = existing.get(candidate.candidate_id, {}).get("row_number")
            if existing_row_number:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A{existing_row_number}:Q{existing_row_number}",
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
                range=f"{self.sheet_name}!A:Q",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": append_rows},
            ).execute()

        return {"updated": updates, "inserted": inserts}

    def _existing_rows_by_candidate_id(self) -> dict[str, dict]:
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A:Q",
        ).execute()
        values = response.get("values", [])
        if len(values) <= 1:
            return {}
        header = values[0]
        rows = values[1:]
        header_index = {name: index for index, name in enumerate(header)}
        candidate_id_index = header_index.get("candidate_id")
        if candidate_id_index is None:
            return {}
        existing: dict[str, dict] = {}
        for offset, row in enumerate(rows, start=2):
            if candidate_id_index >= len(row):
                continue
            candidate_id = row[candidate_id_index].strip()
            if not candidate_id:
                continue
            existing[candidate_id] = {
                "row_number": offset,
                "review_decision": self._value_at(row, header_index, "review_decision"),
                "review_notes": self._value_at(row, header_index, "review_notes"),
                "approved_source_id": self._value_at(row, header_index, "approved_source_id"),
            }
        return existing

    @staticmethod
    def _merge_existing_state(record: dict[str, str], existing: dict | None) -> dict[str, str]:
        if not existing:
            return record
        for field in ["review_decision", "review_notes", "approved_source_id"]:
            if existing.get(field):
                record[field] = existing[field]
        return record
