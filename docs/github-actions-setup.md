# GitHub Actions Setup

This is the recommended Phase 1 deployment path.

## Step 1: Create a GitHub repo

1. Create a new private GitHub repository.
2. Name it something like `localist-phase1-raton`.
3. Do not initialize it with a README if you plan to push this repo as-is.

## Step 2: Connect this local repo to GitHub

Run these commands from the repo root after you create the GitHub repo:

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git add .
git commit -m "Initial Phase 1 scaffold"
git push -u origin main
```

If a remote already exists, use:

```bash
git remote set-url origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## Step 3: Create a Google service account

1. Create a Google Cloud project or use an existing one.
2. Enable Google Sheets API.
3. Create a service account for this pipeline.
4. Create a JSON key for that service account.
5. Create the review Google Sheet.
6. Share the sheet with the service account email as an editor.

## Step 4: Add GitHub repository secrets

Add these repository secrets in GitHub:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  Paste the full JSON credentials.
- `GOOGLE_SHEETS_SPREADSHEET_ID`
  The spreadsheet ID from the Google Sheet URL.

Optional future secrets:

- `OPENAI_API_KEY`
- `SOURCE_SCOUT_ENABLED`

## Step 5: Enable the workflow

The repo includes a starter workflow at `.github/workflows/daily_phase1.yml`.

It currently supports:

- manual runs with `workflow_dispatch`
- daily scheduled runs via cron

## Step 6: Verify the first run

1. Open the repo in GitHub.
2. Go to `Actions`.
3. Open `Daily Phase 1 Ingestion`.
4. Run it manually once.
5. Confirm the workflow loads config correctly.
6. After Sheets integration is added, confirm that the review tab receives rows.

## Recommended next implementation

After the repo is on GitHub, the next code step should be:

1. connect Google Sheets write access
2. preserve `review_status` across reruns
3. add first-pass source fetching for the three pilot sources

