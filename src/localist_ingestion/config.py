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
