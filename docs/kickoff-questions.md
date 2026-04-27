# Kickoff Questions

These are the remaining questions I need answered to make the first working version useful.

1. Which Google account or workspace should own the review sheet?
   Recommendation: use a dedicated Google service account and share the sheet with that account.

2. What counts as disallowed or high-risk?
   Recommendation: write these as plain-language review rules, not legal policy language.

3. Should source scouting be part of the same cadence?
   Recommendation: keep event ingestion daily and run source scouting weekly so it does not increase false positives in the core queue.

4. What is the preferred GitHub repo destination?
   Recommendation: create a dedicated private repo for Phase 1 so credentials and workflow history stay isolated.
