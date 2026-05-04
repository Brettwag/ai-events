from __future__ import annotations

from pathlib import Path
import tomllib

from .models import RuntimeConfig, SourceConfig


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_runtime_config(config_dir: Path) -> RuntimeConfig:
    raw = load_toml(config_dir / "runtime.toml")
    return RuntimeConfig(
        name=raw["project"]["name"],
        time_zone=raw["project"]["time_zone"],
        cadence=raw["project"]["cadence"],
        run_time_local=raw["project"]["run_time_local"],
        review_sheet_name=raw["project"]["review_sheet_name"],
        source_scout_sheet_name=raw["project"]["source_scout_sheet_name"],
        ai_event_scout_sheet_name=raw["project"]["ai_event_scout_sheet_name"],
        geography=raw["pilot"]["geography"],
        radius_miles_min=int(raw["pilot"]["radius_miles_min"]),
        radius_miles_max=int(raw["pilot"]["radius_miles_max"]),
        geography_notes=raw["pilot"]["geography_notes"],
        minimum_required_fields=raw["quality"]["minimum_required_fields"],
        minimum_required_location_fields=raw["quality"]["minimum_required_location_fields"],
        lookahead_days=int(raw["quality"]["lookahead_days"]),
        minimum_confidence_score=float(raw["quality"]["minimum_confidence_score"]),
        drop_low_confidence_candidates=bool(raw["quality"]["drop_low_confidence_candidates"]),
        allowed_statuses=raw["review"]["allowed_statuses"],
        default_status=raw["review"]["default_status"],
        enable_google_sheets=bool(raw["export"]["enable_google_sheets"]),
        enable_ics_export=bool(raw["export"]["enable_ics_export"]),
        export_only_approved_rows=bool(raw["export"]["export_only_approved_rows"]),
        source_scout_enabled=bool(raw["source_scout"]["enabled"]),
        source_scout_model=raw["source_scout"]["model"],
        source_scout_reasoning_effort=raw["source_scout"]["reasoning_effort"],
        source_scout_max_candidates_per_run=int(raw["source_scout"]["max_candidates_per_run"]),
        source_scout_search_region=raw["source_scout"]["search_region"],
        source_scout_search_radius_miles=int(raw["source_scout"]["search_radius_miles"]),
        approved_domains=list(raw["source_scout"]["approved_domains"]),
        ai_event_scout_enabled=bool(raw["ai_event_scout"]["enabled"]),
        ai_event_scout_model=raw["ai_event_scout"]["model"],
        ai_event_scout_reasoning_effort=raw["ai_event_scout"]["reasoning_effort"],
        ai_event_scout_max_events_per_run=int(raw["ai_event_scout"]["max_events_per_run"]),
        ai_event_scout_search_region=raw["ai_event_scout"]["search_region"],
        ai_event_scout_search_radius_miles=int(raw["ai_event_scout"]["search_radius_miles"]),
        ai_event_scout_minimum_trust_level=raw["ai_event_scout"]["minimum_trust_level"],
        ai_event_scout_max_passes=int(raw["ai_event_scout"]["max_passes"]),
        ai_event_scout_stop_after_consecutive_empty_passes=int(
            raw["ai_event_scout"]["stop_after_consecutive_empty_passes"]
        ),
        ai_event_scout_query_focuses=list(raw["ai_event_scout"]["query_focuses"]),
    )


def load_sources(config_dir: Path) -> list[SourceConfig]:
    raw = load_toml(config_dir / "sources.toml")
    sources = []
    for item in raw.get("sources", []):
        sources.append(
            SourceConfig(
                id=item["id"],
                label=item["label"],
                enabled=bool(item["enabled"]),
                type=item["type"],
                discovery_mode=item["discovery_mode"],
                base_url=item["base_url"],
                seed_urls=list(item.get("seed_urls", [])),
                source_organization=item["source_organization"],
                geography_tags=list(item.get("geography_tags", [])),
                notes=item.get("notes", ""),
            )
        )
    return sources


def load_taxonomy(config_dir: Path) -> dict:
    return load_toml(config_dir / "taxonomy.toml")
