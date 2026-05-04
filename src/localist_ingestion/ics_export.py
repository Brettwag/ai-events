from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .models import RuntimeConfig
from .review_queue import GoogleSheetsReviewQueue


@dataclass(slots=True)
class ApprovedEventRecord:
    record_id: str
    sheet_name: str
    event_title: str
    start_date: str
    start_time: str
    end_date: str
    end_time: str
    venue_name: str
    address: str
    city: str
    state: str
    description: str
    event_url: str
    source_url: str
    source_name: str
    duplicate_key: str


def build_approved_events_ics(runtime: RuntimeConfig, repo_root: Path) -> str:
    events = dedupe_events(load_approved_events(runtime=runtime, repo_root=repo_root))
    return render_ics_calendar(events=events, calendar_name=f"{runtime.name} Approved Events", time_zone=runtime.time_zone)


def write_approved_events_ics(runtime: RuntimeConfig, repo_root: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_approved_events_ics(runtime=runtime, repo_root=repo_root), encoding="utf-8")
    return output_path


def write_pages_site(runtime: RuntimeConfig, repo_root: Path, output_dir: Path, public_ics_url: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_approved_events_ics(runtime=runtime, repo_root=repo_root, output_path=output_dir / "approved-events.ics")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "index.html").write_text(build_index_html(runtime=runtime, public_ics_url=public_ics_url), encoding="utf-8")
    return output_dir


def load_approved_events(runtime: RuntimeConfig, repo_root: Path) -> list[ApprovedEventRecord]:
    sheet_names = [
        runtime.review_sheet_name,
        runtime.source_scout_sheet_name,
        runtime.ai_event_scout_sheet_name,
    ]
    approved: list[ApprovedEventRecord] = []
    for sheet_name in sheet_names:
        queue = GoogleSheetsReviewQueue(runtime=runtime, repo_root=repo_root, sheet_name=sheet_name)
        for record in queue.list_records():
            if record.get("record_type", "event") != "event":
                continue
            if record.get("review_status", "").strip() != "Approved":
                continue
            if not _is_truthy(record.get("approved_for_export", "")):
                continue
            approved.append(
                ApprovedEventRecord(
                    record_id=record.get("record_id", ""),
                    sheet_name=sheet_name,
                    event_title=record.get("event_title", ""),
                    start_date=record.get("start_date", ""),
                    start_time=record.get("start_time", ""),
                    end_date=record.get("end_date", ""),
                    end_time=record.get("end_time", ""),
                    venue_name=record.get("venue_name", ""),
                    address=record.get("address", ""),
                    city=record.get("city", ""),
                    state=record.get("state", ""),
                    description=record.get("description", ""),
                    event_url=record.get("event_url", ""),
                    source_url=record.get("source_url", ""),
                    source_name=record.get("source_organization", "") or record.get("source_domain", ""),
                    duplicate_key=record.get("duplicate_key", ""),
                )
            )
    return approved


def dedupe_events(events: Iterable[ApprovedEventRecord]) -> list[ApprovedEventRecord]:
    deduped: list[ApprovedEventRecord] = []
    seen: set[str] = set()
    for event in events:
        key = event.duplicate_key or "|".join(
            [
                event.event_title.strip().lower(),
                event.start_date.strip(),
                event.start_time.strip(),
                event.venue_name.strip().lower(),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def render_ics_calendar(events: list[ApprovedEventRecord], calendar_name: str, time_zone: str) -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Events//Approved Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics_text(calendar_name)}",
        f"X-WR-TIMEZONE:{time_zone}",
    ]

    for event in events:
        lines.extend(render_event_lines(event=event, dtstamp=now, time_zone=time_zone))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_index_html(runtime: RuntimeConfig, public_ics_url: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html_escape(runtime.name)} ICS Feed</title>
    <style>
      body {{
        margin: 0;
        font-family: Inter, system-ui, sans-serif;
        background: #f8fafc;
        color: #0f172a;
      }}
      main {{
        max-width: 760px;
        margin: 64px auto;
        padding: 0 24px;
      }}
      .card {{
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 28px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 28px;
      }}
      p {{
        margin: 0 0 18px;
        line-height: 1.5;
        color: #475569;
      }}
      code {{
        display: block;
        padding: 12px 14px;
        border-radius: 12px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        overflow-x: auto;
      }}
      a.button {{
        display: inline-block;
        margin-top: 16px;
        padding: 10px 14px;
        border-radius: 10px;
        background: #2563eb;
        color: white;
        text-decoration: none;
        font-weight: 600;
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="card">
        <h1>{html_escape(runtime.name)} Approved Events Feed</h1>
        <p>This GitHub Pages site publishes the latest ICS feed built from approved spreadsheet rows.</p>
        <code>{html_escape(public_ics_url)}</code>
        <a class="button" href="approved-events.ics">Open approved-events.ics</a>
      </div>
    </main>
  </body>
</html>
"""


def render_event_lines(event: ApprovedEventRecord, dtstamp: str, time_zone: str) -> list[str]:
    title = event.event_title.strip() or "Untitled event"
    description_parts = [part for part in [event.description.strip(), event.source_url.strip()] if part]
    description = "\n\n".join(description_parts)
    location = ", ".join(part for part in [event.venue_name, event.address, event.city, event.state] if part)
    url = event.event_url.strip() or event.source_url.strip()

    start_date = parse_date(event.start_date)
    end_date = parse_date(event.end_date) if event.end_date else None
    start_time = parse_time(event.start_time)
    end_time = parse_time(event.end_time)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{escape_ics_text(event.record_id or f'{title}-{event.start_date}')}@ai-events.local",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{escape_ics_text(title)}",
        f"STATUS:CONFIRMED",
    ]
    if description:
        lines.append(f"DESCRIPTION:{escape_ics_text(description)}")
    if location:
        lines.append(f"LOCATION:{escape_ics_text(location)}")
    if url:
        lines.append(f"URL:{escape_ics_text(url)}")

    if start_time:
        tz = ZoneInfo(time_zone)
        start_dt = datetime.combine(start_date, start_time, tzinfo=tz)
        lines.append(f"DTSTART;TZID={time_zone}:{start_dt.strftime('%Y%m%dT%H%M%S')}")
        if end_time:
            end_dt = datetime.combine(end_date or start_date, end_time, tzinfo=tz)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(hours=2)
            lines.append(f"DTEND;TZID={time_zone}:{end_dt.strftime('%Y%m%dT%H%M%S')}")
    else:
        lines.append(f"DTSTART;VALUE=DATE:{start_date.strftime('%Y%m%d')}")
        exclusive_end = (end_date or start_date) + timedelta(days=1)
        lines.append(f"DTEND;VALUE=DATE:{exclusive_end.strftime('%Y%m%d')}")

    lines.append("END:VEVENT")
    return lines


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str) -> time | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) == 5:
        cleaned = f"{cleaned}:00"
    return time.fromisoformat(cleaned)


def escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}
