from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import RuntimeConfig
from .schema import column_letter, load_review_queue_columns


def _import_google_clients() -> tuple[object, object]:
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Sheets dependencies are not installed. Run `pip install -r requirements.txt` first."
        ) from exc
    return Credentials, build


def load_google_service_account_info() -> dict:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc


def load_spreadsheet_id() -> str:
    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        raise RuntimeError("Missing GOOGLE_SHEETS_SPREADSHEET_ID environment variable.")
    return spreadsheet_id


class GoogleSheetsReviewQueue:
    def __init__(self, runtime: RuntimeConfig, repo_root: Path) -> None:
        credentials_cls, build = _import_google_clients()
        service_account_info = load_google_service_account_info()
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = credentials_cls.from_service_account_info(service_account_info, scopes=scopes)
        self.service = build("sheets", "v4", credentials=credentials)
        self.spreadsheet_id = load_spreadsheet_id()
        self.sheet_name = runtime.review_sheet_name
        self.columns = load_review_queue_columns(repo_root)
        self.last_column = column_letter(len(self.columns))

    def ensure_sheet_ready(self) -> None:
        sheet_names = self._sheet_names()
        if self.sheet_name not in sheet_names:
            self._create_sheet(self.sheet_name)
        self._ensure_header()

    def upsert_candidates(self, candidates: list[Any], run_date: str) -> dict[str, int]:
        self.ensure_sheet_ready()
        existing = self._existing_rows_by_record_id()
        updates = 0
        inserts = 0
        append_rows: list[list[str]] = []

        for candidate in candidates:
            record = candidate.to_sheet_record(run_date)
            record_id = record.get("record_id", "")
            row_values = self._record_to_row(
                self._merge_existing_state(record, existing.get(record_id))
            )
            existing_row_number = existing.get(record_id, {}).get("row_number")
            if existing_row_number:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A{existing_row_number}:{self.last_column}{existing_row_number}",
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
                range=f"{self.sheet_name}!A:{self.last_column}",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": append_rows},
            ).execute()

        return {"updated": updates, "inserted": inserts}

    def _sheet_names(self) -> set[str]:
        metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        return {
            sheet["properties"]["title"]
            for sheet in metadata.get("sheets", [])
            if "properties" in sheet and "title" in sheet["properties"]
        }

    def _create_sheet(self, title: str) -> None:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()

    def _ensure_header(self) -> None:
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!1:1",
        ).execute()
        current_header = response.get("values", [[]])[0] if response.get("values") else []
        if current_header != self.columns:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!1:1",
                valueInputOption="RAW",
                body={"values": [self.columns]},
            ).execute()

    def _existing_rows_by_record_id(self) -> dict[str, dict]:
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A:{self.last_column}",
        ).execute()
        values = response.get("values", [])
        if len(values) <= 1:
            return {}

        header = values[0]
        rows = values[1:]
        header_index = {name: index for index, name in enumerate(header)}
        record_id_index = header_index.get("record_id")
        if record_id_index is None:
            return {}

        existing: dict[str, dict] = {}
        for offset, row in enumerate(rows, start=2):
            if record_id_index >= len(row):
                continue
            record_id = row[record_id_index].strip()
            if not record_id:
                continue
            existing[record_id] = {
                "row_number": offset,
                "review_status": self._value_at(row, header_index, "review_status"),
                "reviewer_notes": self._value_at(row, header_index, "reviewer_notes"),
                "approved_for_export": self._value_at(row, header_index, "approved_for_export"),
                "approved_source_id": self._value_at(row, header_index, "approved_source_id"),
                "promote_to_main_queue": self._value_at(row, header_index, "promote_to_main_queue"),
            }
        return existing

    @staticmethod
    def _merge_existing_state(record: dict[str, str], existing: dict | None) -> dict[str, str]:
        if not existing:
            return record
        if existing.get("review_status"):
            record["review_status"] = existing["review_status"]
        if existing.get("reviewer_notes"):
            record["reviewer_notes"] = existing["reviewer_notes"]
        if existing.get("approved_for_export"):
            record["approved_for_export"] = existing["approved_for_export"]
        if existing.get("approved_source_id"):
            record["approved_source_id"] = existing["approved_source_id"]
        if existing.get("promote_to_main_queue"):
            record["promote_to_main_queue"] = existing["promote_to_main_queue"]
        return record

    def _record_to_row(self, record: dict[str, str]) -> list[str]:
        return [record.get(column, "") for column in self.columns]

    @staticmethod
    def _value_at(row: list[str], header_index: dict[str, int], column: str) -> str:
        index = header_index.get(column)
        if index is None or index >= len(row):
            return ""
        return row[index]
