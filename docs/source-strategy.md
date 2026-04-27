# Source Strategy

This project should use two separate source pools.

## 1. Approved daily sources

These are the sites the daily ingestion job always checks.

Characteristics:

- official or trusted
- event-focused
- reasonably parseable
- low false-positive risk

Current approved examples live in [config/sources.toml](/Users/brettwagner/ai-events/config/sources.toml).

## 2. Candidate weekly sources

These are sites the source scout proposes for approval.

Characteristics:

- likely relevant to Raton or the surrounding pilot geography
- may be parseable but not yet trusted
- may overlap with existing sources
- should not feed the daily review queue until approved

Current candidates live in [config/source_candidates.toml](/Users/brettwagner/ai-events/config/source_candidates.toml).

## Recommended operating model

Daily:

- ingest only approved sources
- optimize for precision
- keep the review sheet manageable

Weekly:

- search for new official calendars, venues, museums, tourism sites, theaters, nonprofits, schools, and government event pages
- score each source for trust, event density, and parser difficulty
- add promising finds to the candidate registry
- promote selected candidates into the approved source registry after human approval

## What I need from you

I do not need you to manually hunt for every source.

I do need:

1. approval or rejection on proposed source shortlists
2. any must-have organizations you already know matter locally
3. any source types you want excluded

## Immediate recommendation

The next two approved sources I would add are:

1. `Historic Shuler Theater`
2. `NRA Whittington Center Events`

Those look like the cleanest high-signal additions for more event coverage without a big precision penalty.
