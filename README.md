# solar-quote-form-data

Proposed data fields for a solar quote request form, with a Python script that cleans and checks submissions.

This repo proposes extra fields and metadata for a solar quote request form so submissions stay consistent for storage, search, and later AI use. It includes a single-file proposal page and a small Python script that normalizes contact data, assigns stable IDs, flags likely duplicates and bad data, and links duplicates without merging or deleting records.

**View the proposal:** https://igormajdov.github.io/solar-quote-form-data/

All data in this repo is fake: `555-01xx` phone numbers, `example.com` emails, and made-up addresses.

## What's here

| Path | What it is |
|---|---|
| `docs/index.html` | The proposal as a tabbed page: overview, current vs. proposed form, field table, sample record, data flow. A single file with no dependencies. |
| `scripts/quote_check.py` | The code sample. It cleans and checks quote submissions (CSV in, JSON out). |
| `data/sample_submissions.csv` | 8 fake submissions, seeded with typical problems. |
| `tests/test_quote_check.py` | Unit tests (standard library `unittest`). |
| `.claude/skills/check-quotes/SKILL.md` | A Claude Code skill that runs the script and reports its results. |
| `ai-transcript.md` | The conversation with Claude Code used to build this repo. |

## The script

`quote_check.py` uses only the Python standard library (3.9+). For each submission it:

- **normalizes** the phone to E.164 (`+13145550101`), lowercases and trims the email, and uppercases the street with USPS abbreviations (`Street`→`ST`). It also maps state names to 2-letter codes, cuts ZIP+4 to 5 digits, and converts the timestamp to UTC.
- **adds** a stable `submission_id`, which is a hash of the normalized email, phone, address and time, so re-running gives the same IDs. It also sets `source`, defaulting to `web_form`.
- **flags** invalid email, phone or ZIP, a missing or zone-less timestamp, and addresses outside Missouri and Illinois.
- **marks likely duplicates**: if the normalized email, phone, or street+ZIP matches an earlier submission, it sets `duplicate_of` (the earlier ID) and `matched_on`. It never merges or deletes anything.

Output is repeatable: the same CSV always produces byte-identical JSON. Pass `--now` only if you want a `processed_at` time.

```bash
# run on the sample data (JSON to stdout, summary to stderr)
python3 scripts/quote_check.py data/sample_submissions.csv

# write to a file
python3 scripts/quote_check.py data/sample_submissions.csv -o checked_submissions.json

# run the tests
python3 -m unittest discover tests
```

Expected summary for the sample file:

```
8 submissions: 4 clean, 2 likely duplicates, flags {'invalid_email': 1, 'invalid_phone': 1, 'outside_service_area': 1}
```

Known limits: phone numbers are US-only. Address handling is light normalization for matching, not USPS validation, and a production version would call an address-verification API. Duplicate detection uses exact keys, not fuzzy matching.

## The Claude skill

In Claude Code, from the repo root, ask "check the quote submissions" or run `/check-quotes`. The skill calls `scripts/quote_check.py` and reports the summary and the flagged records, using only what the script returned. The skill doesn't do the checks itself, so results are the same every time.

## Viewing the page

Open `docs/index.html` in a browser. To publish it, go to the repo's **Settings → Pages**, set Source to *Deploy from a branch*, pick `main` / `/docs`, and save.
