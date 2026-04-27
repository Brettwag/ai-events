from __future__ import annotations

from pathlib import Path

from .config import load_runtime_config, load_sources, load_taxonomy


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


def main() -> None:
    print(summarize_scaffold())


if __name__ == "__main__":
    main()
