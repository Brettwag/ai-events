# Local Admin App

This repo now includes a local-first admin app for operating the pilot without hand-editing TOML files.

## What it does today

- edit core runtime inputs
- edit approved daily sources
- inspect candidate sources
- inspect workflow lanes

## What it does not do yet

- direct Google Sheets review actions
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
