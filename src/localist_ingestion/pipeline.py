from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .config import load_runtime_config, load_sources, load_taxonomy
from .ics_export import write_approved_events_ics, write_pages_site
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
    events, results = discover_events(sources, runtime=runtime, today=date.today())

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


def run_weekly_source_scout() -> str:
    from .source_scout import run_source_scout
    from .source_scout_queue import GoogleSheetsSourceScoutQueue

    root = repo_root()
    config_dir = root / "config"
    runtime = load_runtime_config(config_dir)
    if not runtime.source_scout_enabled:
        return "Source scout is disabled."
    sources = load_sources(config_dir)
    candidates = run_source_scout(
        runtime=runtime,
        sources=sources,
        prompt_path=root / "prompts" / "source_scout.md",
    )
    lines = [f"Source scout produced {len(candidates)} candidate sources."]
    if runtime.enable_google_sheets:
        queue = GoogleSheetsSourceScoutQueue(runtime=runtime, repo_root=root)
        counts = queue.upsert_candidates(candidates, run_date=date.today().isoformat())
        lines.append(f"Scout queue upsert complete: inserted={counts['inserted']}, updated={counts['updated']}")
    for candidate in candidates[:5]:
        lines.append(f"- {candidate.label} | {candidate.base_url} | {candidate.status_recommendation}")
    return "\n".join(lines)


def run_ai_event_scout() -> str:
    from .ai_event_scout_queue import GoogleSheetsAIEventScoutQueue
    from .event_scout import run_ai_event_scout as run_scout

    root = repo_root()
    config_dir = root / "config"
    runtime = load_runtime_config(config_dir)
    if not runtime.ai_event_scout_enabled:
        return "AI event scout is disabled."
    sources = load_sources(config_dir)
    candidates = run_scout(
        runtime=runtime,
        sources=sources,
        repo_root=root,
        prompt_path=root / "prompts" / "event_scout.md",
    )
    lines = [f"AI event scout produced {len(candidates)} event candidates."]
    if runtime.enable_google_sheets:
        queue = GoogleSheetsAIEventScoutQueue(runtime=runtime, repo_root=root)
        counts = queue.upsert_candidates(candidates, run_date=date.today().isoformat())
        lines.append(f"AI event scout queue upsert complete: inserted={counts['inserted']}, updated={counts['updated']}")
    for candidate in candidates[:5]:
        lines.append(f"- {candidate.event_title} | {candidate.start_date} | {candidate.source_domain} | {candidate.trust_level}")
    return "\n".join(lines)


def export_approved_ics(output_path: Path | None = None) -> str:
    root = repo_root()
    config_dir = root / "config"
    runtime = load_runtime_config(config_dir)
    if not runtime.enable_ics_export:
        return "ICS export is disabled."
    target = output_path or (root / "exports" / "approved-events.ics")
    written = write_approved_events_ics(runtime=runtime, repo_root=root, output_path=target)
    return f"Approved events ICS written to {written}"


def export_pages_site(output_dir: Path, public_ics_url: str) -> str:
    root = repo_root()
    config_dir = root / "config"
    runtime = load_runtime_config(config_dir)
    if not runtime.enable_ics_export:
        return "ICS export is disabled."
    written = write_pages_site(runtime=runtime, repo_root=root, output_dir=output_dir, public_ics_url=public_ics_url)
    return f"GitHub Pages site written to {written}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 Localist ingestion scaffold utilities.")
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=[
            "summary",
            "init-review-sheet",
            "run-discovery",
            "run-source-scout",
            "run-ai-event-scout",
            "export-approved-ics",
            "export-pages-site",
        ],
        help="Action to perform.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path for ICS export.",
    )
    parser.add_argument(
        "--public-ics-url",
        help="Public ICS URL to embed in the generated Pages site.",
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
    if args.command == "run-source-scout":
        print(run_weekly_source_scout())
        return
    if args.command == "run-ai-event-scout":
        print(run_ai_event_scout())
        return
    if args.command == "export-approved-ics":
        output_path = Path(args.output).expanduser() if args.output else None
        print(export_approved_ics(output_path=output_path))
        return
    if args.command == "export-pages-site":
        if not args.output or not args.public_ics_url:
            raise SystemExit("export-pages-site requires --output and --public-ics-url")
        output_dir = Path(args.output).expanduser()
        print(export_pages_site(output_dir=output_dir, public_ics_url=args.public_ics_url))
        return
    print(summarize_scaffold())


if __name__ == "__main__":
    main()
