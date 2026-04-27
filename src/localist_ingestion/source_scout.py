from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha1
import json
from pathlib import Path

from .models import RuntimeConfig, SourceConfig
from .openai_client import create_response, first_output_text, first_refusal


SCOUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "base_url": {"type": "string"},
                    "seed_url": {"type": "string"},
                    "source_organization": {"type": "string"},
                    "geography_tags": {"type": "array", "items": {"type": "string"}},
                    "source_type": {"type": "string"},
                    "trust_level": {"type": "string", "enum": ["high", "medium", "low"]},
                    "event_density": {"type": "string", "enum": ["high", "medium", "low", "unknown"]},
                    "parser_difficulty": {"type": "string", "enum": ["easy", "medium", "hard", "unknown"]},
                    "reason_to_include": {"type": "string"},
                    "evidence": {"type": "string"},
                    "status_recommendation": {"type": "string", "enum": ["recommended", "candidate", "reject"]},
                },
                "required": [
                    "label",
                    "base_url",
                    "seed_url",
                    "source_organization",
                    "geography_tags",
                    "source_type",
                    "trust_level",
                    "event_density",
                    "parser_difficulty",
                    "reason_to_include",
                    "evidence",
                    "status_recommendation",
                ],
            },
        }
    },
    "required": ["candidates"],
}


@dataclass(slots=True)
class SourceScoutCandidate:
    candidate_id: str
    label: str
    base_url: str
    seed_url: str
    source_organization: str
    geography_tags: list[str]
    source_type: str
    trust_level: str
    event_density: str
    parser_difficulty: str
    reason_to_include: str
    evidence: str
    status_recommendation: str

    def to_sheet_record(self, run_date: str) -> dict[str, str]:
        return {
            "run_date": run_date,
            "candidate_id": self.candidate_id,
            "label": self.label,
            "base_url": self.base_url,
            "seed_url": self.seed_url,
            "source_organization": self.source_organization,
            "geography_tags": "; ".join(self.geography_tags),
            "source_type": self.source_type,
            "trust_level": self.trust_level,
            "event_density": self.event_density,
            "parser_difficulty": self.parser_difficulty,
            "reason_to_include": self.reason_to_include,
            "evidence": self.evidence,
            "status_recommendation": self.status_recommendation,
            "review_decision": "",
            "review_notes": "",
            "approved_source_id": "",
        }


def run_source_scout(
    *,
    runtime: RuntimeConfig,
    sources: list[SourceConfig],
    prompt_path: Path,
) -> list[SourceScoutCandidate]:
    prompt = prompt_path.read_text(encoding="utf-8")
    approved_domains = sorted({domain_from_url(source.base_url) for source in sources} | set(runtime.approved_domains))
    payload = {
        "model": runtime.source_scout_model,
        "reasoning": {"effort": runtime.source_scout_reasoning_effort},
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
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": build_scout_request(runtime, approved_domains),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "source_scout_results",
                "strict": True,
                "schema": SCOUT_SCHEMA,
            }
        },
    }
    response = create_response(payload)
    refusal = first_refusal(response)
    if refusal:
        raise RuntimeError(f"Source scout refused the request: {refusal}")

    text = first_output_text(response)
    if not text:
        raise RuntimeError("Source scout returned no structured text.")

    raw = json.loads(text)
    return parse_candidates(raw.get("candidates", []), approved_domains, runtime.source_scout_max_candidates_per_run)


def build_scout_request(runtime: RuntimeConfig, approved_domains: list[str]) -> str:
    return (
        f"Find up to {runtime.source_scout_max_candidates_per_run} new event-source websites for "
        f"{runtime.source_scout_search_region} and the surrounding {runtime.source_scout_search_radius_miles} mile area. "
        "Return only sources that are not already approved. "
        f"Already approved domains: {', '.join(approved_domains)}. "
        "Prefer official calendars, theaters, arts organizations, museums, government calendars, libraries, schools, parks, and trusted community organizations. "
        "Do not return event listings; return websites or calendars that should be considered as sources."
    )


def parse_candidates(raw_candidates: list[dict], approved_domains: list[str], limit: int) -> list[SourceScoutCandidate]:
    seen_domains: set[str] = set(approved_domains)
    parsed: list[SourceScoutCandidate] = []

    for item in raw_candidates:
        base_url = item["base_url"].strip()
        domain = domain_from_url(base_url)
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        candidate_id = sha1(base_url.encode("utf-8")).hexdigest()[:16]
        parsed.append(
            SourceScoutCandidate(
                candidate_id=candidate_id,
                label=item["label"].strip(),
                base_url=base_url,
                seed_url=item["seed_url"].strip(),
                source_organization=item["source_organization"].strip(),
                geography_tags=[tag.strip() for tag in item["geography_tags"] if tag.strip()],
                source_type=item["source_type"].strip(),
                trust_level=item["trust_level"].strip(),
                event_density=item["event_density"].strip(),
                parser_difficulty=item["parser_difficulty"].strip(),
                reason_to_include=item["reason_to_include"].strip(),
                evidence=item["evidence"].strip(),
                status_recommendation=item["status_recommendation"].strip(),
            )
        )
        if len(parsed) >= limit:
            break
    return parsed


def domain_from_url(url: str) -> str:
    cleaned = url.replace("https://", "").replace("http://", "").strip().rstrip("/")
    return cleaned.split("/", 1)[0].lower()
