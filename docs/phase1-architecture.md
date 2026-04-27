# Phase 1 Architecture

## What we are building

Phase 1 is a narrow, human-in-the-loop ingestion workflow:

1. Read an approved list of pilot sources.
2. Discover candidate event URLs on a daily cadence.
3. Extract event details into a canonical schema.
4. Classify visibility, source sector, target sector, and risk.
5. Write one event per row to a Google Sheet for human review.
6. Later, export only approved rows to ICS for Localist upload.

## Why config-first matters

The PRD explicitly says geography, source list, and taxonomy should be configurable over time. That means the easiest things to edit should live outside code:

- Source registry in `config/sources.toml`
- Taxonomy and review rules in `config/taxonomy.toml`
- Runtime schedule, geography, and review thresholds in `config/runtime.toml`
- Agent instructions in `prompts/*.md`

Code should mostly orchestrate those decisions, not own them.

## Recommended agent split

### 1. Discovery agent

Responsibilities:

- Read approved source definitions
- Visit seed URLs or feeds
- Collect candidate event URLs
- Preserve provenance

Editable surfaces:

- Source definitions
- Discovery prompt
- Per-source notes

### 2. Extraction agent

Responsibilities:

- Parse event page content
- Produce canonical event fields
- Mark missing required fields
- Preserve source URL and source organization

Editable surfaces:

- Extraction prompt
- Required field list
- Per-source extraction hints

### 3. Classification agent

Responsibilities:

- Infer source sector
- Infer target sector
- Infer public vs invite-only
- Flag risky, disallowed, low-confidence, or duplicate-looking events

Editable surfaces:

- Taxonomy config
- Classification prompt
- Risk flag list

### 4. Review/export agent

Responsibilities:

- Upsert rows into Google Sheets
- Keep review status intact across reruns
- Prepare approved rows for later ICS export

Editable surfaces:

- Review schema
- Status vocabulary
- Output mapping rules

## Scheduling recommendation

For this project, GitHub Actions is the current recommendation because:

1. Daily cadence is a natural fit for cron-based workflows.
2. The pipeline is still narrow and human-reviewed.
3. Secrets for Google Sheets access can be stored as repository secrets.
4. It keeps Phase 1 cheap and easy to inspect.

## Google Sheets review queue

The sheet should optimize for fast review, not for raw ingestion detail. A practical column set is:

- `event_id`
- `run_date`
- `source_id`
- `source_organization`
- `source_url`
- `event_url`
- `event_title`
- `start_date`
- `start_time`
- `end_date`
- `end_time`
- `venue_name`
- `address`
- `city`
- `state`
- `description`
- `source_sector`
- `target_sector`
- `visibility`
- `confidence_score`
- `risk_flags`
- `missing_fields`
- `duplicate_key`
- `review_status`
- `reviewer_notes`
- `approved_for_export`

## ICS handoff

The PRD keeps publishing manual in Phase 1, which is the right constraint.

The cleanest handoff is:

1. Review happens in one main Google Sheet tab.
2. Only rows with `review_status = Approved` and `approved_for_export = TRUE` are exported.
3. A small ICS exporter turns those rows into calendar events.
4. Localist ingests the ICS feed or ICS file manually.

That keeps the risk boundary simple: no event gets close to Localist until a human approves it.

## Suggested treatment of source scouting

You mentioned wanting the agent to go find more sources. I recommend splitting that from daily event ingestion:

1. Daily agent:
   only uses approved pilot sources and feeds the review queue
2. Weekly source scout:
   searches for additional event websites, directories, or calendars in the Raton area and proposes them for approval

That separation preserves the PRD's precision-first rule while still making the system smarter over time.
