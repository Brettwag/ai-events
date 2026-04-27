from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha1
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from .models import EventCandidate, SourceConfig


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class SourceRunResult:
    source_id: str
    discovered: int
    emitted: int
    skipped: int
    notes: list[str]


MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE_WITH_YEAR_RE = re.compile(rf"\b({MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}}\b", re.IGNORECASE)
DATE_WITHOUT_YEAR_RE = re.compile(rf"\b({MONTH_PATTERN})\s+\d{{1,2}}\b", re.IGNORECASE)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?|am|pm)\b", re.IGNORECASE)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def discover_events(sources: list[SourceConfig], today: date | None = None) -> tuple[list[EventCandidate], list[SourceRunResult]]:
    today = today or date.today()
    session = build_session()
    all_events: list[EventCandidate] = []
    results: list[SourceRunResult] = []

    for source in sources:
        if not source.enabled:
            continue
        handler = SOURCE_HANDLERS.get(source.id, discover_generic_source)
        try:
            events, notes = handler(session, source, today)
        except Exception as exc:
            results.append(
                SourceRunResult(
                    source_id=source.id,
                    discovered=0,
                    emitted=0,
                    skipped=0,
                    notes=[f"Source failed: {exc}"],
                )
            )
            continue
        filtered = [event for event in events if is_candidate_usable(event, today)]
        skipped = len(events) - len(filtered)
        all_events.extend(filtered)
        results.append(
            SourceRunResult(
                source_id=source.id,
                discovered=len(events),
                emitted=len(filtered),
                skipped=skipped,
                notes=notes,
            )
        )
    return dedupe_events(all_events), results


def discover_raton_mainstreet(session: requests.Session, source: SourceConfig, today: date) -> tuple[list[EventCandidate], list[str]]:
    url = source.seed_urls[0]
    html = fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")
    notes: list[str] = []

    cards = soup.select("article, .tribe-events-calendar-list__event-row, .ect-list-post, li")
    events: list[EventCandidate] = []
    seen_urls: set[str] = set()

    for card in cards:
        anchor = card.find("a", href=True)
        if anchor is None:
            continue
        event_url = normalize_url(url, anchor["href"])
        if "/event/" not in event_url or event_url in seen_urls:
            continue
        seen_urls.add(event_url)

        title = normalize_space(anchor.get_text(" ", strip=True))
        if not title or title.lower() == "subscribe to calendar":
            continue

        card_text = normalize_space(card.get_text(" ", strip=True))
        start_date = first_iso_date_from_text(card_text)
        start_time = first_time_from_text(card_text)
        venue_name = extract_mainstreet_venue(card_text, title)
        description = extract_description_from_text(card_text, title, venue_name)

        event = build_candidate(
            source=source,
            event_url=event_url,
            event_title=title,
            start_date=start_date,
            start_time=start_time,
            venue_name=venue_name,
            description=description,
            source_url=event_url,
            confidence_score=0.88 if start_date else 0.62,
        )
        if not start_date:
            event.missing_fields.append("start_date")
            event.risk_flags.append("Missing key fields")
        if not venue_name:
            event.missing_fields.append("location")
        events.append(event)

    notes.append(f"Parsed {len(events)} event cards from {url}.")
    return events, notes


def discover_explore_raton(session: requests.Session, source: SourceConfig, today: date) -> tuple[list[EventCandidate], list[str]]:
    url = source.seed_urls[0]
    html = fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")
    notes: list[str] = []

    roundup_links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_url(url, anchor["href"])
        if "/post/" not in href:
            continue
        text = normalize_space(anchor.get_text(" ", strip=True))
        if "event roundup" in text.lower() or "events in raton" in text.lower():
            roundup_links.append(href)

    roundup_links = unique_preserve_order(roundup_links)[:2]
    events: list[EventCandidate] = []

    for roundup_url in roundup_links:
        try:
            roundup_html = fetch_html(session, roundup_url)
        except requests.RequestException as exc:
            notes.append(f"Skipped roundup {roundup_url}: {exc}")
            continue
        roundup_events = parse_explore_roundup(source, roundup_url, roundup_html, today)
        notes.append(f"Parsed {len(roundup_events)} events from {roundup_url}.")
        events.extend(roundup_events)

    if not roundup_links:
        notes.append("No roundup links were found on the Explore Raton events page.")
    return events, notes


def discover_generic_source(session: requests.Session, source: SourceConfig, today: date) -> tuple[list[EventCandidate], list[str]]:
    url = source.seed_urls[0]
    html = fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")
    notes = ["Using generic discovery heuristics."]
    events: list[EventCandidate] = []

    anchors = soup.find_all("a", href=True)
    seen: set[str] = set()
    for anchor in anchors:
        href = normalize_url(url, anchor["href"])
        if href in seen or not looks_like_event_link(href, anchor.get_text(" ", strip=True)):
            continue
        seen.add(href)
        parent_text = normalize_space(anchor.parent.get_text(" ", strip=True)) if isinstance(anchor.parent, Tag) else ""
        start_date = first_iso_date_from_text(parent_text)
        if not start_date:
            continue
        title = normalize_space(anchor.get_text(" ", strip=True))
        event = build_candidate(
            source=source,
            event_url=href,
            event_title=title,
            start_date=start_date,
            start_time=first_time_from_text(parent_text),
            source_url=href,
            description=parent_text,
            confidence_score=0.55,
        )
        events.append(event)

    notes.append(f"Generic discovery produced {len(events)} candidates from {url}.")
    return events, notes


def parse_explore_roundup(source: SourceConfig, roundup_url: str, html: str, today: date) -> list[EventCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    post_title = ""
    title_node = soup.find(["h1", "title"])
    if title_node:
        post_title = normalize_space(title_node.get_text(" ", strip=True))

    publication_year = parse_year_from_text(post_title) or today.year
    candidates: list[EventCandidate] = []
    heading_nodes = soup.find_all(["h4", "h3"])

    for heading in heading_nodes:
        title = normalize_space(heading.get_text(" ", strip=True))
        if not title or len(title) < 3:
            continue
        lines: list[str] = []
        more_info_url = roundup_url
        node = heading.find_next_sibling()
        while node is not None and getattr(node, "name", None) not in {"h3", "h4"}:
            text = normalize_space(node.get_text(" ", strip=True))
            if text:
                lines.append(text)
            if isinstance(node, Tag):
                info_link = node.find("a", href=True)
                if info_link is not None:
                    more_info_url = normalize_url(roundup_url, info_link["href"])
            node = node.find_next_sibling()

        if not lines:
            continue

        date_line = lines[0]
        location_line = lines[1] if len(lines) > 1 else ""
        description = " ".join(lines[2:]).strip()
        start_date = parse_roundup_date(date_line, publication_year)
        start_time = first_time_from_text(date_line)

        event = build_candidate(
            source=source,
            event_url=more_info_url,
            event_title=title,
            start_date=start_date,
            start_time=start_time,
            venue_name=location_line,
            description=description,
            source_url=roundup_url,
            confidence_score=0.78 if start_date else 0.5,
        )
        if not start_date:
            event.missing_fields.append("start_date")
            event.risk_flags.append("Missing key fields")
        if not location_line:
            event.missing_fields.append("location")
        candidates.append(event)

    return candidates


def build_candidate(
    *,
    source: SourceConfig,
    event_url: str,
    event_title: str,
    start_date: str,
    start_time: str = "",
    venue_name: str = "",
    address: str = "",
    city: str = "Raton",
    state: str = "NM",
    description: str = "",
    source_url: str = "",
    confidence_score: float = 0.7,
) -> EventCandidate:
    source_url = source_url or event_url
    event_id_seed = "|".join([source.id, event_url or source_url, event_title, start_date, venue_name])
    return EventCandidate(
        event_id=sha1(event_id_seed.encode("utf-8")).hexdigest()[:16],
        source_id=source.id,
        source_url=source_url,
        event_url=event_url,
        event_title=event_title,
        start_date=start_date,
        start_time=start_time,
        venue_name=venue_name,
        address=address,
        city=city if venue_name or address else "",
        state=state if venue_name or address else "",
        description=description,
        source_organization=source.source_organization,
        confidence_score=confidence_score,
        duplicate_key=make_duplicate_key(event_title, start_date, venue_name),
    )


def is_candidate_usable(event: EventCandidate, today: date) -> bool:
    required_ok = bool(event.event_title and event.start_date and event.source_url)
    location_ok = bool(event.venue_name or event.address or event.city)
    if not required_ok or not location_ok:
        return False
    try:
        start = date.fromisoformat(event.start_date)
    except ValueError:
        return False
    return start >= today


def dedupe_events(events: Iterable[EventCandidate]) -> list[EventCandidate]:
    deduped: dict[str, EventCandidate] = {}
    for event in events:
        existing = deduped.get(event.duplicate_key)
        if existing is None or event.confidence_score > existing.confidence_score:
            deduped[event.duplicate_key] = event
    return list(deduped.values())


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href.strip())


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def first_iso_date_from_text(text: str) -> str:
    text = normalize_space(text)
    match = DATE_WITH_YEAR_RE.search(text)
    if not match:
        return ""
    parsed = parse_date_token(match.group(0))
    return parsed.isoformat() if parsed else ""


def first_time_from_text(text: str) -> str:
    match = TIME_RE.search(text)
    if not match:
        return ""
    cleaned = match.group(0).lower().replace(".", "")
    for fmt in ("%I:%M %p",):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return ""


def extract_mainstreet_venue(card_text: str, title: str) -> str:
    cleaned = card_text.replace(title, "", 1)
    cleaned = re.sub(rf"{DATE_WITH_YEAR_RE.pattern}.*?(?=[A-Z][a-z]+|$)", "", cleaned, flags=re.IGNORECASE)
    pieces = [piece.strip(" -") for piece in cleaned.split("  ") if piece.strip()]
    if pieces:
        venue = pieces[0]
        if len(venue) <= 80 and not DATE_WITH_YEAR_RE.search(venue):
            return venue
    return ""


def extract_description_from_text(card_text: str, title: str, venue_name: str) -> str:
    text = normalize_space(card_text)
    for token in [title, venue_name]:
        if token:
            text = text.replace(token, "", 1)
    if len(text) > 400:
        return text[:397].rstrip() + "..."
    return text


def parse_roundup_date(text: str, default_year: int) -> str:
    normalized = normalize_space(text)
    normalized = re.sub(r"\bat\s+\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?\b", "", normalized, flags=re.IGNORECASE)
    full = first_iso_date_from_text(normalized)
    if full:
        return full

    same_month_range = re.match(rf"^({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})$", normalized, re.IGNORECASE)
    if same_month_range:
        month_name = same_month_range.group(1)
        start_day = same_month_range.group(2)
        token = f"{month_name} {start_day}, {default_year}"
        parsed = parse_date_token(token)
        return parsed.isoformat() if parsed else ""

    single = DATE_WITHOUT_YEAR_RE.search(normalized)
    if single:
        token = f"{single.group(0)}, {default_year}"
        parsed = parse_date_token(token)
        return parsed.isoformat() if parsed else ""

    return ""


def parse_date_token(token: str) -> date | None:
    cleaned = token.replace("Sept", "Sep")
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def parse_year_from_text(text: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", text)
    return int(match.group(1)) if match else None


def make_duplicate_key(title: str, start_date: str, venue_name: str) -> str:
    return normalize_space(f"{title}|{start_date}|{venue_name}").lower()


def looks_like_event_link(href: str, text: str) -> bool:
    joined = f"{href} {text}".lower()
    return any(token in joined for token in ["event", "calendar", "festival", "concert", "show", "roundup"])


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


SOURCE_HANDLERS = {
    "raton-mainstreet": discover_raton_mainstreet,
    "explore-raton-events": discover_explore_raton,
}
