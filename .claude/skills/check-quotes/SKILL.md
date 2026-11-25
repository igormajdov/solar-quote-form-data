---
name: check-quotes
description: Clean and check a CSV of solar quote request submissions (normalize phone, email and address, add stable IDs, flag likely duplicates and bad data) by running scripts/quote_check.py. Use when asked to check, clean, validate or dedupe quote submissions.
allowed-tools: Bash(python3 scripts/quote_check.py:*), Read
---

# Check quote submissions

All checks are done by `scripts/quote_check.py`. Your job is to run it and report what it found. Do not redo or "improve" the checks yourself, so the results stay repeatable.

## Steps

1. Choose the input CSV. If the user didn't name one, use `data/sample_submissions.csv`.
2. From the repo root, run:

   ```bash
   python3 scripts/quote_check.py <csv> -o checked_submissions.json
   ```

   Add `--now <UTC ISO timestamp>` only if the user asks for a processing time. Without it the output is fully repeatable.
3. If the command fails, show the error exactly and stop. Don't guess at results.
4. Read `checked_submissions.json` and report:
   - the one-line summary the script printed
   - a short table of every record that has `flags` or a `duplicate_of`, with columns `submission_id`, name, `flags`, `matched_on`, `duplicate_of`
5. Use only values from the JSON. Don't edit the CSV or the output, and don't merge or delete records. Deciding what to do with duplicates is a human's call.
