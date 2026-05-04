from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tomllib
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "admin" / "web"
CONFIG_ROOT = REPO_ROOT / "config"


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
    return [
        {
            "id": "daily_phase1",
            "name": "Daily Approved-Source Discovery",
            "sheet": "Phase 1 Review Queue",
            "purpose": "Higher-trust daily event discovery from approved sources.",
        },
        {
            "id": "weekly_source_scout",
            "name": "Weekly Source Scout",
            "sheet": "Source Scout Queue",
            "purpose": "AI-assisted search for new source websites and calendars.",
        },
        {
            "id": "daily_ai_event_scout",
            "name": "Daily AI Event Scout",
            "sheet": "AI Event Scout Queue",
            "purpose": "Broader, higher-recall search for actual event candidates.",
        },
    ]


class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
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
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self.read_json_body()
        if parsed.path == "/api/runtime":
            save_runtime(body)
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/sources":
            save_sources(body.get("sources", []))
            self.send_json({"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

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

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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
