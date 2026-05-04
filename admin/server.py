from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tomllib
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "admin" / "web"
CONFIG_ROOT = REPO_ROOT / "config"
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from localist_ingestion.config import load_runtime_config
from localist_ingestion.ics_export import build_approved_events_ics
from localist_ingestion.review_queue import GoogleSheetsReviewQueue


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_runtime() -> dict:
    return load_toml(CONFIG_ROOT / "runtime.toml")


def load_sources() -> list[dict]:
    raw = load_toml(CONFIG_ROOT / "sources.toml")
    return list(raw.get("sources", []))


def load_source_candidates() -> list[dict]:
    raw = load_toml(CONFIG_ROOT / "source_candidates.toml")
    return list(raw.get("candidates", []))


def save_runtime(payload: dict) -> None:
    runtime = {
        "project": {
            "name": payload["project"]["name"],
            "time_zone": payload["project"]["time_zone"],
            "cadence": payload["project"]["cadence"],
            "run_time_local": payload["project"]["run_time_local"],
            "review_sheet_name": payload["project"]["review_sheet_name"],
            "source_scout_sheet_name": payload["project"]["source_scout_sheet_name"],
            "ai_event_scout_sheet_name": payload["project"]["ai_event_scout_sheet_name"],
        },
        "pilot": {
            "geography": payload["pilot"]["geography"],
            "radius_miles_min": int(payload["pilot"]["radius_miles_min"]),
            "radius_miles_max": int(payload["pilot"]["radius_miles_max"]),
            "geography_notes": payload["pilot"]["geography_notes"],
        },
        "quality": {
            "minimum_required_fields": payload["quality"]["minimum_required_fields"],
            "minimum_required_location_fields": payload["quality"]["minimum_required_location_fields"],
            "lookahead_days": int(payload["quality"]["lookahead_days"]),
            "minimum_confidence_score": float(payload["quality"]["minimum_confidence_score"]),
            "drop_low_confidence_candidates": bool(payload["quality"]["drop_low_confidence_candidates"]),
        },
        "review": {
            "allowed_statuses": payload["review"]["allowed_statuses"],
            "default_status": payload["review"]["default_status"],
        },
        "export": {
            "enable_google_sheets": bool(payload["export"]["enable_google_sheets"]),
            "enable_ics_export": bool(payload["export"]["enable_ics_export"]),
            "export_only_approved_rows": bool(payload["export"]["export_only_approved_rows"]),
        },
        "source_scout": {
            "enabled": bool(payload["source_scout"]["enabled"]),
            "model": payload["source_scout"]["model"],
            "reasoning_effort": payload["source_scout"]["reasoning_effort"],
            "max_candidates_per_run": int(payload["source_scout"]["max_candidates_per_run"]),
            "search_region": payload["source_scout"]["search_region"],
            "search_radius_miles": int(payload["source_scout"]["search_radius_miles"]),
            "approved_domains": payload["source_scout"]["approved_domains"],
        },
        "ai_event_scout": {
            "enabled": bool(payload["ai_event_scout"]["enabled"]),
            "model": payload["ai_event_scout"]["model"],
            "reasoning_effort": payload["ai_event_scout"]["reasoning_effort"],
            "max_events_per_run": int(payload["ai_event_scout"]["max_events_per_run"]),
            "search_region": payload["ai_event_scout"]["search_region"],
            "search_radius_miles": int(payload["ai_event_scout"]["search_radius_miles"]),
            "minimum_trust_level": payload["ai_event_scout"]["minimum_trust_level"],
            "max_passes": int(payload["ai_event_scout"]["max_passes"]),
            "stop_after_consecutive_empty_passes": int(
                payload["ai_event_scout"]["stop_after_consecutive_empty_passes"]
            ),
            "query_focuses": payload["ai_event_scout"]["query_focuses"],
            "source_type_focuses": payload["ai_event_scout"]["source_type_focuses"],
        },
    }
    text = render_runtime_toml(runtime)
    (CONFIG_ROOT / "runtime.toml").write_text(text, encoding="utf-8")


def save_sources(sources: list[dict]) -> None:
    text = render_sources_toml(sources)
    (CONFIG_ROOT / "sources.toml").write_text(text, encoding="utf-8")


def render_runtime_toml(raw: dict) -> str:
    lines: list[str] = []
    for section_name in [
        "project",
        "pilot",
        "quality",
        "review",
        "export",
        "source_scout",
        "ai_event_scout",
    ]:
        lines.append(f"[{section_name}]")
        for key, value in raw[section_name].items():
            lines.extend(render_toml_key_value(key, value))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_sources_toml(sources: list[dict]) -> str:
    lines: list[str] = []
    for source in sources:
        lines.append("[[sources]]")
        for key in [
            "id",
            "label",
            "enabled",
            "type",
            "discovery_mode",
            "base_url",
            "seed_urls",
            "source_organization",
            "geography_tags",
            "notes",
        ]:
            lines.extend(render_toml_key_value(key, source.get(key)))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_toml_key_value(key: str, value: object) -> list[str]:
    if isinstance(value, bool):
        return [f"{key} = {'true' if value else 'false'}"]
    if isinstance(value, (int, float)):
        return [f"{key} = {value}"]
    if isinstance(value, list):
        lines = [f"{key} = ["]
        for item in value:
            lines.append(f'  "{escape_toml_string(str(item))}",')
        lines.append("]")
        return lines
    return [f'{key} = "{escape_toml_string(str(value or ""))}"']


def escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def workflow_status() -> list[dict]:
    runtime = load_runtime()
    return [
        {
            "id": "daily_phase1",
            "name": "Daily Approved-Source Discovery",
            "sheet": runtime["project"]["review_sheet_name"],
            "purpose": "Higher-trust daily event discovery from approved sources.",
        },
        {
            "id": "weekly_source_scout",
            "name": "Weekly Source Scout",
            "sheet": runtime["project"]["source_scout_sheet_name"],
            "purpose": "AI-assisted search for new source websites and calendars.",
        },
        {
            "id": "daily_ai_event_scout",
            "name": "Daily AI Event Scout",
            "sheet": runtime["project"]["ai_event_scout_sheet_name"],
            "purpose": "Broader, higher-recall search for actual event candidates.",
        },
    ]


def review_sheet_specs(runtime: object) -> list[dict[str, str]]:
    return [
        {
            "workflow_id": "daily_phase1",
            "sheet_name": runtime.review_sheet_name,
            "label": "Approved Queue",
        },
        {
            "workflow_id": "weekly_source_scout",
            "sheet_name": runtime.source_scout_sheet_name,
            "label": "Source Scout Queue",
        },
        {
            "workflow_id": "daily_ai_event_scout",
            "sheet_name": runtime.ai_event_scout_sheet_name,
            "label": "AI Event Scout Queue",
        },
    ]


def load_review_queue_payload(sort_key: str = "date") -> dict:
    runtime = load_runtime_config(CONFIG_ROOT)
    review_rows: list[dict] = []
    lane_stats: list[dict] = []

    for spec in review_sheet_specs(runtime):
        queue = GoogleSheetsReviewQueue(runtime=runtime, repo_root=REPO_ROOT, sheet_name=spec["sheet_name"])
        raw_rows = queue.list_records()
        event_rows = [row for row in raw_rows if row.get("record_type", "event") == "event"]
        review_rows.extend(review_row_from_record(row, spec, runtime.allowed_statuses, runtime.default_status) for row in event_rows)
        lane_stats.append(
            {
                "workflow_id": spec["workflow_id"],
                "sheet_name": spec["sheet_name"],
                "label": spec["label"],
                "total_rows": len(raw_rows),
                "event_rows": len(event_rows),
            }
        )

    review_rows.sort(key=review_sorter(sort_key))
    return {
        "rows": review_rows,
        "sort_key": sort_key,
        "sort_options": [
            {"value": "date", "label": "Date"},
            {"value": "source", "label": "Source"},
        ],
        "lane_stats": lane_stats,
        "allowed_statuses": runtime.allowed_statuses,
    }


def save_review_queue_updates(payload: dict) -> dict:
    runtime = load_runtime_config(CONFIG_ROOT)
    allowed_statuses = set(runtime.allowed_statuses)
    updates_by_sheet: dict[str, list[dict]] = {}

    for item in payload.get("updates", []):
        record_id = str(item.get("record_id", "")).strip()
        sheet_name = str(item.get("sheet_name", "")).strip()
        review_status = str(item.get("review_status") or runtime.default_status)
        if not record_id or not sheet_name:
            continue
        if review_status not in allowed_statuses:
            raise ValueError(f"Invalid review status: {review_status}")
        updates_by_sheet.setdefault(sheet_name, []).append(
            {
                "record_id": record_id,
                "review_status": review_status,
                "approved_for_export": bool(item.get("approved_for_export")),
                "reviewer_notes": str(item.get("reviewer_notes", "") or ""),
            }
        )

    updated = 0
    missing: list[str] = []
    for sheet_name, updates in updates_by_sheet.items():
        queue = GoogleSheetsReviewQueue(runtime=runtime, repo_root=REPO_ROOT, sheet_name=sheet_name)
        result = queue.update_review_records(updates)
        updated += int(result.get("updated", 0))
        missing.extend(result.get("missing", []))

    return {"ok": True, "updated": updated, "missing": missing}


def approved_events_ics() -> str:
    runtime = load_runtime_config(CONFIG_ROOT)
    if not runtime.enable_ics_export:
        raise RuntimeError("ICS export is disabled in config/runtime.toml.")
    return build_approved_events_ics(runtime=runtime, repo_root=REPO_ROOT)


def review_row_from_record(record: dict, spec: dict[str, str], allowed_statuses: list[str], default_status: str) -> dict:
    source_name = record.get("source_organization") or record.get("source_domain") or spec["label"]
    return {
        "record_id": record.get("record_id", ""),
        "record_type": record.get("record_type", ""),
        "sheet_name": spec["sheet_name"],
        "workflow_id": spec["workflow_id"],
        "queue_label": spec["label"],
        "source_name": source_name,
        "source_method": record.get("source_method", ""),
        "source_organization": record.get("source_organization", ""),
        "source_domain": record.get("source_domain", ""),
        "source_url": record.get("source_url", ""),
        "event_url": record.get("event_url", ""),
        "event_title": record.get("event_title", ""),
        "start_date": record.get("start_date", ""),
        "start_time": record.get("start_time", ""),
        "end_date": record.get("end_date", ""),
        "end_time": record.get("end_time", ""),
        "venue_name": record.get("venue_name", ""),
        "address": record.get("address", ""),
        "city": record.get("city", ""),
        "state": record.get("state", ""),
        "description": record.get("description", ""),
        "trust_level": record.get("trust_level", ""),
        "confidence_score": record.get("confidence_score", ""),
        "status_recommendation": record.get("status_recommendation", ""),
        "risk_flags": split_multivalue_field(record.get("risk_flags", "")),
        "missing_fields": split_multivalue_field(record.get("missing_fields", "")),
        "review_status": record.get("review_status") or default_status,
        "approved_for_export": is_truthy(record.get("approved_for_export", "")),
        "reviewer_notes": record.get("reviewer_notes", ""),
        "allowed_statuses": allowed_statuses,
    }


def split_multivalue_field(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def review_sorter(sort_key: str):
    if sort_key == "source":
        return lambda row: (
            row.get("source_name", "").lower(),
            row.get("start_date") or "9999-99-99",
            row.get("event_title", "").lower(),
        )
    return lambda row: (
        row.get("start_date") or "9999-99-99",
        row.get("start_time") or "99:99",
        row.get("source_name", "").lower(),
        row.get("event_title", "").lower(),
    )


class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/runtime":
                self.send_json(load_runtime())
                return
            if parsed.path == "/api/sources":
                self.send_json({"sources": load_sources()})
                return
            if parsed.path == "/api/source-candidates":
                self.send_json({"candidates": load_source_candidates()})
                return
            if parsed.path == "/api/workflows":
                self.send_json({"workflows": workflow_status()})
                return
            if parsed.path == "/api/review-queue":
                sort_key = query.get("sort", ["date"])[0]
                self.send_json(load_review_queue_payload(sort_key=sort_key))
                return
            if parsed.path == "/api/approved-events.ics":
                self.send_ics(approved_events_ics(), filename="approved-events.ics")
                return
            self.serve_static(parsed.path)
        except RuntimeError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            body = self.read_json_body()
            if parsed.path == "/api/runtime":
                save_runtime(body)
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/sources":
                save_sources(body.get("sources", []))
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/review-queue":
                self.send_json(save_review_queue_updates(body))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "Invalid JSON payload."}, status=HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        file_path = (WEB_ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(WEB_ROOT)) or not file_path.exists() or file_path.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        content_type = guess_content_type(file_path)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_ics(self, payload: str, filename: str) -> None:
        data = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


def guess_content_type(path: Path) -> str:
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    if path.suffix == ".json":
        return "application/json; charset=utf-8"
    return "text/html; charset=utf-8"


def main() -> None:
    port = int(os.environ.get("AI_EVENTS_ADMIN_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), AdminHandler)
    print(f"Local admin app running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
