# Local Admin App

This repo now includes a local-first admin app for operating the pilot without hand-editing TOML files.

## What it does today

- edit core runtime inputs
- merge live workflow rows into one review table
- save review decisions back to the spreadsheet
- expose approved events as an ICS feed
- edit approved daily sources
- inspect candidate sources
- inspect workflow lanes

## What it does not do yet

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

To read the live workflow tabs and write review decisions back to the same spreadsheet rows, start the server with:

```bash
export GOOGLE_SHEETS_SPREADSHEET_ID="your_spreadsheet_id"
export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="/Users/brettwagner/ai-events/google-service-account.json"
python3.11 admin/server.py
```

The server also accepts `GOOGLE_SERVICE_ACCOUNT_JSON` if you prefer passing the raw JSON as an environment variable.

## Approved-events ICS feed

Once event rows are marked `review_status = Approved` and `approved_for_export = TRUE`, the local app exposes:

```text
http://127.0.0.1:8765/api/approved-events.ics
```

You can open that feed directly from the `Review` toolbar.

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
- the three workflow tabs in Google Sheets when credentials are available
