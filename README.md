# City of Raton Phase 1

This repo is a config-first starter for Phase 1 of the AI event ingestion workflow described in the PRD.

Phase 1 goal: discover events from approved sources on a daily cadence, extract structured fields, flag risky or incomplete items, and write one event per row to a Google Sheet for human review.

The design bias in this repo is:

- Keep agent behavior editable through prompt files and config files.
- Keep source onboarding lightweight so new sources do not require code changes unless the source is unusual.
- Keep publishing manual in Phase 1.
- Keep ICS export downstream from approved rows only.

## Repo layout

- `config/`: runtime, source, and taxonomy configuration
- `config/source_candidates.toml`: weekly source-scout registry
- `prompts/`: editable prompt text for discovery, extraction, and classification
- `schemas/`: machine-readable review queue schema
- `src/localist_ingestion/`: starter Python package for orchestration
- `docs/`: architecture notes and kickoff questions

## Recommended Phase 1 boundary

1. Discovery agent reads approved source config and finds likely event pages.
2. Extraction agent turns those pages into a consistent event schema.
3. Classification agent adds confidence, risk flags, and taxonomy labels.
4. Review exporter writes rows to Google Sheets.
5. A separate Phase 1.5 step exports only approved rows to ICS.

## What works now

- Config-driven source list, taxonomy, and runtime settings
- Editable prompts for discovery, extraction, and classification
- GitHub Actions starter workflow
- Google Sheets review-tab initializer using repo secrets
- First-pass rule-based discovery for the three pilot sources

## Google Sheets secrets

The workflow expects these GitHub repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Once those are set, the workflow can create or repair the main review tab header automatically.

## Current discovery boundary

The first-pass implementation is intentionally conservative:

- `Raton MainStreet`:
  parses the events listing page directly
- `Explore Raton`:
  parses event roundup posts into one event per row
- `City of Raton Calendar`:
  currently uses generic heuristics until we tune it against the live page structure

This is the right Phase 1 tradeoff because precision matters more than recall.

## Review-window policy

The review queue uses a configurable future lookahead window in [config/runtime.toml](/Users/brettwagner/ai-events/config/runtime.toml).

- Current default: `180` days
- Good Phase 1 range: `180` to `365` days

This keeps the sheet focused on events that are actionable enough for near-term review.

## Source growth model

Use two pools:

- approved daily sources in [config/sources.toml](/Users/brettwagner/ai-events/config/sources.toml)
- candidate weekly sources in [config/source_candidates.toml](/Users/brettwagner/ai-events/config/source_candidates.toml)

See [docs/source-strategy.md](/Users/brettwagner/ai-events/docs/source-strategy.md) for the recommended workflow.

## Current Phase 1 choices

1. Recurring job: GitHub Actions
2. Initial pilot sources:
   `https://ratonmainstreet.org/events/`
   `https://ratonnm.gov/calendar.php`
   `https://www.exploreraton.com/events`
3. Pilot geography:
   Raton plus a practical surrounding area, initially treated as roughly 50-100 miles with human review bias toward caution
4. Required review fields:
   `event_title`
   `start_date`
   `source_url`
   at least one usable location field such as `venue_name`, `address`, or `city`
5. Review output:
   one main Google Sheets review tab

## Next decisions

1. Which Google account or workspace should own the review sheet and service account access?
2. What counts as disallowed or high-risk?
3. Do you want source scouting for new event websites in the same Phase 1 workflow, or as a separate weekly agent?
