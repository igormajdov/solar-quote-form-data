#!/usr/bin/env python3
"""Clean and check solar quote request submissions.

Reads a CSV export of quote requests, normalizes phone, email and address,
gives each record a stable ID, flags likely duplicates and data problems,
and writes the result as JSON. Same input always gives the same output.

Usage:
    python3 scripts/quote_check.py data/sample_submissions.csv
    python3 scripts/quote_check.py data/sample_submissions.csv -o out.json
    python3 scripts/quote_check.py data/sample_submissions.csv --now 2026-11-25T18:00:00Z
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

SERVICE_STATES = {"MO", "IL"}
STATE_NAMES = {"MISSOURI": "MO", "ILLINOIS": "IL", "KANSAS": "KS", "IOWA": "IA"}
# Common USPS abbreviations; enough for matching, not a full address standardizer.
STREET_WORDS = {
    "STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN",
    "COURT": "CT", "BOULEVARD": "BLVD", "PLACE": "PL", "CIRCLE": "CIR",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
DUPLICATE_KEYS = ("email", "phone", "address_key")


def normalize_phone(raw):
    """Return a US phone number in E.164 form (+13145550101), or None."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return "+1" + digits if len(digits) == 10 else None


def normalize_email(raw):
    """Trim and lowercase; return None if it doesn't look like an email."""
    email = (raw or "").strip().lower()
    return email if EMAIL_RE.match(email) else None


def _clean_text(raw):
    """Uppercase, drop periods and commas, collapse whitespace."""
    return " ".join(re.sub(r"[.,]", " ", raw or "").upper().split())


def normalize_street(raw):
    return " ".join(STREET_WORDS.get(word, word) for word in _clean_text(raw).split())


def normalize_state(raw):
    state = _clean_text(raw)
    return STATE_NAMES.get(state, state) if state else None


def normalize_zip(raw):
    match = re.match(r"\d{5}", (raw or "").strip())
    return match.group() if match else None


def normalize_timestamp(raw):
    """Parse an ISO-8601 timestamp and return it in UTC as ...Z, or None."""
    text = (raw or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None  # a time without a zone is ambiguous, so don't guess
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_row(row, now=None):
    """Turn one raw CSV row into a cleaned record with a list of flags."""
    flags = []
    raw_time = (row.get("received_at") or "").strip()
    received_at = normalize_timestamp(raw_time) if raw_time else now
    if received_at is None:
        flags.append("invalid_received_at" if raw_time else "missing_received_at")

    record = {
        "submission_id": None,
        "received_at": received_at,
        "source": (row.get("source") or "").strip().lower() or "web_form",
        "first_name": " ".join((row.get("first_name") or "").split()),
        "last_name": " ".join((row.get("last_name") or "").split()),
        "email": normalize_email(row.get("email")),
        "phone": normalize_phone(row.get("phone")),
        "street": normalize_street(row.get("street")) or None,
        "city": _clean_text(row.get("city")) or None,
        "state": normalize_state(row.get("state")),
        "zip": normalize_zip(row.get("zip")),
    }
    if record["email"] is None:
        flags.append("invalid_email")
    if record["phone"] is None:
        flags.append("invalid_phone")
    if record["zip"] is None:
        flags.append("invalid_zip")
    if record["state"] not in SERVICE_STATES:
        flags.append("outside_service_area")

    # Address key for matching: only when we have both a street and a ZIP.
    has_address = record["street"] and record["zip"]
    record["address_key"] = f"{record['street']}|{record['zip']}" if has_address else None

    id_source = "|".join(str(record[k] or "") for k in ("email", "phone", "address_key", "received_at"))
    record["submission_id"] = "Q-" + hashlib.sha256(id_source.encode()).hexdigest()[:12]
    record["flags"] = flags
    return record


def find_duplicates(records):
    """Mark records whose email, phone or address matches an earlier record."""
    first_seen = {}  # (key, value) -> submission_id of the earliest record
    for record in records:
        matches = {}
        for key in DUPLICATE_KEYS:
            value = record[key]
            if value is None:
                continue
            if (key, value) in first_seen:
                matches[key] = first_seen[(key, value)]
            else:
                first_seen[(key, value)] = record["submission_id"]
        record["matched_on"] = sorted(matches)
        record["duplicate_of"] = matches[min(matches, key=DUPLICATE_KEYS.index)] if matches else None
    return records


def check_file(path, now=None):
    with open(path, newline="", encoding="utf-8") as f:
        records = [clean_row(row, now) for row in csv.DictReader(f)]
    # Oldest first, so "duplicate_of" always points at the earlier submission.
    records.sort(key=lambda r: (r["received_at"] is None, r["received_at"] or ""))
    find_duplicates(records)

    flag_counts = {}
    for record in records:
        for flag in record["flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    summary = {
        "total": len(records),
        "clean": sum(1 for r in records if not r["flags"] and not r["duplicate_of"]),
        "duplicates": sum(1 for r in records if r["duplicate_of"]),
        "flags": dict(sorted(flag_counts.items())),
    }
    result = {"summary": summary, "records": records}
    if now:
        result["processed_at"] = now
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clean and check quote submissions.")
    parser.add_argument("csv_path", help="CSV export of quote submissions")
    parser.add_argument("-o", "--output", help="write JSON here instead of stdout")
    parser.add_argument("--now", help="UTC timestamp to use for processed_at and missing received_at")
    args = parser.parse_args(argv)

    now = normalize_timestamp(args.now) if args.now else None
    if args.now and now is None:
        parser.error("--now must be an ISO-8601 timestamp with a time zone, e.g. 2026-11-25T18:00:00Z")

    result = check_file(args.csv_path, now)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    s = result["summary"]
    line = f"{s['total']} submissions: {s['clean']} clean, {s['duplicates']} likely duplicates, flags {s['flags']}"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(line)
    else:
        sys.stdout.write(text)
        print(line, file=sys.stderr)


if __name__ == "__main__":
    main()
