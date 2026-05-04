# Local Admin App

This repo now includes a local-first admin app for operating the pilot without hand-editing TOML files.

## What it does today

- edit core runtime inputs
- review and approve event rows from the main Google Sheet queue
- edit approved daily sources
- inspect candidate sources
- inspect workflow lanes

## What it does not do yet

- ICS generation
- Localist upload
- triggering GitHub Actions from the UI

## Run locally

From the repo root:

```bash
python3.11 admin/server.py
```

Then open:

```text
http://127.0.0.1:8765
```

Optional custom port:

```bash
AI_EVENTS_ADMIN_PORT=8877 python3.11 admin/server.py
```

## Spreadsheet-backed review mode

The local app can now read and write the same Google Sheet used by the ingestion workflows.
That means:

- Google Sheets remains the detailed source of truth
- the local app shows a narrower review-focused moderation table
- approval decisions written in the app update the existing spreadsheet rows

For that mode, set these environment variables before starting the server:

```bash
export GOOGLE_SHEETS_SPREADSHEET_ID="your_spreadsheet_id"
export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/absolute/path/to/service-account.json"
python3.11 admin/server.py
```

You can also use `GOOGLE_SERVICE_ACCOUNT_JSON` if you prefer passing the full JSON as an environment variable.

## Why this shape

This is intentionally local-first:

- no hosting required
- no cloud setup required
- no frontend build step required
- easy to hand off into a larger team codebase later

## Backing files

The local app currently edits:

- `config/runtime.toml`
- `config/sources.toml`

And it reads:

- `config/source_candidates.toml`
- `Phase 1 Review Queue` in Google Sheets when credentials are available
