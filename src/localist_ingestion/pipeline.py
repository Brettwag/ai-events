from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .config import load_runtime_config, load_sources, load_taxonomy
from .review_queue import GoogleSheetsReviewQueue


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def summarize_scaffold() -> str:
    config_dir = repo_root() / "config"
    runtime = load_runtime_config(config_dir)
    sources = load_sources(config_dir)
    taxonomy = load_taxonomy(config_dir)

    enabled_sources = [source for source in sources if source.enabled]
    risk_flags = taxonomy.get("risk_flags", {}).get("allowed", [])

    lines = [
        f"Project: {runtime.name}",
        f"Cadence: {runtime.cadence} at {runtime.run_time_local} ({runtime.time_zone})",
        f"Pilot geography: {', '.join(runtime.geography) if runtime.geography else 'None set'}",
        f"Geography radius: {runtime.radius_miles_min}-{runtime.radius_miles_max} miles",
        f"Configured sources: {len(sources)} total / {len(enabled_sources)} enabled",
        f"Required fields: {', '.join(runtime.minimum_required_fields)}",
        f"Location requirement: one of {', '.join(runtime.minimum_required_location_fields)}",
        f"Review statuses: {', '.join(runtime.allowed_statuses)}",
        f"Risk flags: {', '.join(risk_flags)}",
        "",
        "Next implementation steps:",
        "1. Replace placeholder source records in config/sources.toml.",
        "2. Connect the discovery stage to approved source pages.",
        "3. Add extraction and classification model calls.",
        "4. Write rows to Google Sheets while preserving review status on reruns.",
        "5. Export only approved rows to ICS.",
    ]
    return "\n".join(lines)


def init_review_sheet() -> str:
    root = repo_root()
    runtime = load_runtime_config(root / "config")
    queue = GoogleSheetsReviewQueue(runtime=runtime, repo_root=root)
    queue.ensure_sheet_ready()
    return f"Review sheet ready: {runtime.review_sheet_name}"


def run_discovery() -> str:
    from .discovery import discover_events

    root = repo_root()
    config_dir = root / "config"
    runtime = load_runtime_config(config_dir)
    sources = load_sources(config_dir)
    events, results = discover_events(sources, today=date.today())

    lines = [
        f"Discovered {len(events)} usable events across {len(results)} enabled sources.",
    ]
    for result in results:
        lines.append(
            f"- {result.source_id}: discovered={result.discovered}, emitted={result.emitted}, skipped={result.skipped}"
        )
        for note in result.notes[:3]:
            lines.append(f"  note: {note}")

    if runtime.enable_google_sheets:
        queue = GoogleSheetsReviewQueue(runtime=runtime, repo_root=root)
        counts = queue.upsert_candidates(events, run_date=date.today().isoformat())
        lines.append(f"Google Sheets upsert complete: inserted={counts['inserted']}, updated={counts['updated']}")

    if events:
        lines.append("")
        lines.append("Sample events:")
        for event in events[:5]:
            lines.append(f"- {event.event_title} | {event.start_date} | {event.venue_name or event.city} | {event.source_url}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 Localist ingestion scaffold utilities.")
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=["summary", "init-review-sheet", "run-discovery"],
        help="Action to perform.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "init-review-sheet":
        print(init_review_sheet())
        return
    if args.command == "run-discovery":
        print(run_discovery())
        return
    print(summarize_scaffold())


if __name__ == "__main__":
    main()
