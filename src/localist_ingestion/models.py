from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(slots=True)
class SourceConfig:
    id: str
    label: str
    enabled: bool
    type: str
    discovery_mode: str
    base_url: str
    seed_urls: list[str]
    source_organization: str
    geography_tags: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(slots=True)
class RuntimeConfig:
    name: str
    time_zone: str
    cadence: str
    run_time_local: str
    review_sheet_name: str
    source_scout_sheet_name: str
    ai_event_scout_sheet_name: str
    geography: list[str]
    radius_miles_min: int
    radius_miles_max: int
    geography_notes: str
    minimum_required_fields: list[str]
    minimum_required_location_fields: list[str]
    lookahead_days: int
    minimum_confidence_score: float
    drop_low_confidence_candidates: bool
    allowed_statuses: list[str]
    default_status: str
    enable_google_sheets: bool
    enable_ics_export: bool
    export_only_approved_rows: bool
    source_scout_enabled: bool
    source_scout_model: str
    source_scout_reasoning_effort: str
    source_scout_max_candidates_per_run: int
    source_scout_search_region: str
    source_scout_search_radius_miles: int
    approved_domains: list[str]
    ai_event_scout_enabled: bool
    ai_event_scout_model: str
    ai_event_scout_reasoning_effort: str
    ai_event_scout_max_events_per_run: int
    ai_event_scout_search_region: str
    ai_event_scout_search_radius_miles: int
    ai_event_scout_minimum_trust_level: str


@dataclass(slots=True)
class EventCandidate:
    event_id: str
    source_id: str
    source_url: str
    event_url: str
    event_title: str = ""
    start_date: str = ""
    start_time: str = ""
    end_date: str = ""
    end_time: str = ""
    venue_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    description: str = ""
    source_organization: str = ""
    source_method: str = "approved_parser"
    source_sector: str = "Unknown"
    target_sector: str = "Unknown"
    visibility: str = "Unknown"
    confidence_score: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    duplicate_key: str = ""
    review_status: str = "Pending"
    reviewer_notes: str = ""
    approved_for_export: bool = False

    def to_sheet_record(self, run_date: str) -> dict[str, str]:
        source_domain = _domain_from_url(self.source_url or self.event_url)
        return {
            "record_id": self.event_id,
            "record_type": "event",
            "source_method": self.source_method,
            "run_date": run_date,
            "source_id": self.source_id,
            "source_organization": self.source_organization,
            "source_domain": source_domain,
            "source_url": self.source_url,
            "event_url": self.event_url,
            "base_url": "",
            "seed_url": "",
            "event_title": self.event_title,
            "start_date": self.start_date,
            "start_time": self.start_time,
            "end_date": self.end_date,
            "end_time": self.end_time,
            "venue_name": self.venue_name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "description": self.description,
            "geography_tags": "",
            "source_type": "",
            "source_sector": self.source_sector,
            "target_sector": self.target_sector,
            "visibility": self.visibility,
            "trust_level": "",
            "confidence_score": f"{self.confidence_score:.2f}" if self.confidence_score else "",
            "event_density": "",
            "parser_difficulty": "",
            "reason_to_include": "",
            "evidence": "",
            "risk_flags": "; ".join(self.risk_flags),
            "missing_fields": "; ".join(self.missing_fields),
            "duplicate_key": self.duplicate_key,
            "status_recommendation": "",
            "review_status": self.review_status or "Pending",
            "reviewer_notes": self.reviewer_notes,
            "approved_for_export": "TRUE" if self.approved_for_export else "FALSE",
            "approved_source_id": "",
            "promote_to_main_queue": "",
        }


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc.lower()
    cleaned = url.replace("https://", "").replace("http://", "").strip().rstrip("/")
    return cleaned.split("/", 1)[0].lower()
