from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha1
import json
from pathlib import Path
import tomllib

from .models import RuntimeConfig, SourceConfig
from .openai_client import create_response, first_output_text, first_refusal
from .source_scout import domain_from_url


EVENT_SCOUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_title": {"type": "string"},
                    "start_date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_date": {"type": "string"},
                    "end_time": {"type": "string"},
                    "venue_name": {"type": "string"},
                    "address": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "description": {"type": "string"},
                    "source_organization": {"type": "string"},
                    "source_domain": {"type": "string"},
                    "source_url": {"type": "string"},
                    "event_url": {"type": "string"},
                    "trust_level": {"type": "string", "enum": ["high", "medium", "low"]},
                    "scout_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reason_to_include": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": [
                    "event_title",
                    "start_date",
                    "start_time",
                    "end_date",
                    "end_time",
                    "venue_name",
                    "address",
                    "city",
                    "state",
                    "description",
                    "source_organization",
                    "source_domain",
                    "source_url",
                    "event_url",
                    "trust_level",
                    "scout_confidence",
                    "reason_to_include",
                    "evidence",
                ],
            },
        }
    },
    "required": ["events"],
}


TRUST_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass(slots=True)
class AIEventScoutCandidate:
    scout_event_id: str
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
    source_organization: str
    source_domain: str
    source_url: str
    event_url: str
    trust_level: str
    scout_confidence: str
    reason_to_include: str
    evidence: str

    def to_sheet_record(self, run_date: str) -> dict[str, str]:
        return {
            "record_id": self.scout_event_id,
            "record_type": "event",
            "source_method": "ai_event_scout",
            "run_date": run_date,
            "source_id": "",
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
            "source_organization": self.source_organization,
            "source_domain": self.source_domain,
            "source_url": self.source_url,
            "event_url": self.event_url,
            "geography_tags": "",
            "source_type": "",
            "source_sector": "",
            "target_sector": "",
            "visibility": "",
            "trust_level": self.trust_level,
            "confidence_score": self.scout_confidence,
            "event_density": "",
            "parser_difficulty": "",
            "reason_to_include": self.reason_to_include,
            "evidence": self.evidence,
            "risk_flags": "",
            "missing_fields": "",
            "duplicate_key": "",
            "status_recommendation": "",
            "review_status": "Pending",
            "reviewer_notes": "",
            "approved_for_export": "",
            "approved_source_id": "",
            "promote_to_main_queue": "",
        }


def run_ai_event_scout(
    *,
    runtime: RuntimeConfig,
    sources: list[SourceConfig],
    repo_root: Path,
    prompt_path: Path,
) -> list[AIEventScoutCandidate]:
    prompt = prompt_path.read_text(encoding="utf-8")
    approved_domains = sorted({domain_from_url(source.base_url) for source in sources} | set(runtime.approved_domains))
    candidate_domains = load_candidate_domains(repo_root / "config" / "source_candidates.toml")
    payload = {
        "model": runtime.ai_event_scout_model,
        "reasoning": {"effort": runtime.ai_event_scout_reasoning_effort},
        "tools": [
            {
                "type": "web_search",
                "user_location": {
                    "type": "approximate",
                    "country": "US",
                    "city": "Raton",
                    "region": "New Mexico",
                    "timezone": runtime.time_zone,
                },
            }
        ],
        "tool_choice": "auto",
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": build_event_scout_request(runtime, approved_domains, candidate_domains),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ai_event_scout_results",
                "strict": True,
                "schema": EVENT_SCOUT_SCHEMA,
            }
        },
    }
    response = create_response(payload)
    refusal = first_refusal(response)
    if refusal:
        raise RuntimeError(f"AI event scout refused the request: {refusal}")
    text = first_output_text(response)
    if not text:
        raise RuntimeError("AI event scout returned no structured text.")
    raw = json.loads(text)
    return parse_events(raw.get("events", []), runtime)


def build_event_scout_request(runtime: RuntimeConfig, approved_domains: list[str], candidate_domains: list[str]) -> str:
    candidate_domains_text = ", ".join(candidate_domains[:20]) if candidate_domains else "none"
    return (
        f"Find up to {runtime.ai_event_scout_max_events_per_run} real upcoming events for "
        f"{runtime.ai_event_scout_search_region} and the surrounding {runtime.ai_event_scout_search_radius_miles} mile area. "
        f"Only include events whose start date is between today and {runtime.lookahead_days} days from today. "
        f"Prefer events from these already-known source domains when useful: {', '.join(approved_domains)}. "
        f"Also consider these candidate domains when they appear relevant: {candidate_domains_text}. "
        "Search broadly beyond those domains if you find trustworthy official event pages. "
        "Return as many legitimate events as possible while preserving source provenance."
    )


def load_candidate_domains(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    domains: list[str] = []
    for item in raw.get("candidates", []):
        base_url = item.get("base_url", "")
        domain = domain_from_url(base_url)
        if domain:
            domains.append(domain)
    return sorted(set(domains))


def parse_events(raw_events: list[dict], runtime: RuntimeConfig) -> list[AIEventScoutCandidate]:
    parsed: list[AIEventScoutCandidate] = []
    seen: set[str] = set()
    minimum_rank = TRUST_RANK.get(runtime.ai_event_scout_minimum_trust_level, 1)

    for item in raw_events:
        trust_level = item["trust_level"].strip().lower()
        if TRUST_RANK.get(trust_level, -1) < minimum_rank:
            continue
        event_title = item["event_title"].strip()
        start_date = item["start_date"].strip()
        source_domain = domain_from_url(item["source_domain"].strip() or item["source_url"].strip())
        event_key = "|".join([event_title.lower(), start_date, source_domain, item["venue_name"].strip().lower()])
        if event_key in seen:
            continue
        seen.add(event_key)
        scout_event_id = sha1(event_key.encode("utf-8")).hexdigest()[:16]
        parsed.append(
            AIEventScoutCandidate(
                scout_event_id=scout_event_id,
                event_title=event_title,
                start_date=start_date,
                start_time=item["start_time"].strip(),
                end_date=item["end_date"].strip(),
                end_time=item["end_time"].strip(),
                venue_name=item["venue_name"].strip(),
                address=item["address"].strip(),
                city=item["city"].strip(),
                state=item["state"].strip(),
                description=item["description"].strip(),
                source_organization=item["source_organization"].strip(),
                source_domain=source_domain,
                source_url=item["source_url"].strip(),
                event_url=item["event_url"].strip(),
                trust_level=trust_level,
                scout_confidence=item["scout_confidence"].strip().lower(),
                reason_to_include=item["reason_to_include"].strip(),
                evidence=item["evidence"].strip(),
            )
        )
        if len(parsed) >= runtime.ai_event_scout_max_events_per_run:
            break
    return parsed
