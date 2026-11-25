import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import quote_check as qc  # noqa: E402

SAMPLE = os.path.join(ROOT, "data", "sample_submissions.csv")


class NormalizeTests(unittest.TestCase):
    def test_phone_formats(self):
        for raw in ["314-555-0101", "(314) 555-0101", "314.555.0101", "+1 314 555 0101", "13145550101"]:
            self.assertEqual(qc.normalize_phone(raw), "+13145550101", raw)
        self.assertIsNone(qc.normalize_phone("314-555-01"))
        self.assertIsNone(qc.normalize_phone(""))

    def test_email(self):
        self.assertEqual(qc.normalize_email("  Priya.N@Example.COM "), "priya.n@example.com")
        self.assertIsNone(qc.normalize_email("casey@example"))
        self.assertIsNone(qc.normalize_email(None))

    def test_address_parts(self):
        self.assertEqual(qc.normalize_street("88 North Kingshighway Street"), "88 N KINGSHIGHWAY ST")
        self.assertEqual(qc.normalize_street("1200  maple ave."), "1200 MAPLE AVE")
        self.assertEqual(qc.normalize_state("Missouri"), "MO")
        self.assertEqual(qc.normalize_zip("63017-1234"), "63017")
        self.assertIsNone(qc.normalize_zip("630"))

    def test_timestamp_to_utc(self):
        self.assertEqual(qc.normalize_timestamp("2026-11-03T10:22:00-06:00"), "2026-11-03T16:22:00Z")
        self.assertIsNone(qc.normalize_timestamp("2026-11-03 10:22"))  # no time zone

    def test_missing_received_at_uses_now(self):
        row = {"email": "a@example.com", "phone": "3145550100", "street": "1 A St", "state": "MO", "zip": "63110"}
        self.assertIn("missing_received_at", qc.clean_row(row)["flags"])
        self.assertEqual(qc.clean_row(row, now="2026-11-25T18:00:00Z")["received_at"], "2026-11-25T18:00:00Z")


class SampleFileTests(unittest.TestCase):
    def setUp(self):
        self.result = qc.check_file(SAMPLE)
        self.by_email = {r["email"]: r for r in self.result["records"]}

    def test_summary_matches_seeded_cases(self):
        self.assertEqual(self.result["summary"], {
            "total": 8, "clean": 4, "duplicates": 2,
            "flags": {"invalid_email": 1, "invalid_phone": 1, "outside_service_area": 1},
        })

    def test_duplicates_point_at_earlier_record(self):
        dups = [r for r in self.result["records"] if r["duplicate_of"]]
        self.assertEqual([r["matched_on"] for r in dups], [["address_key", "email"], ["phone"]])
        original = self.by_email["marcus.ellery@example.com"]
        self.assertEqual(self.by_email["m.ellery@example.com"]["duplicate_of"], original["submission_id"])

    def test_same_input_same_output(self):
        self.assertEqual(qc.check_file(SAMPLE), self.result)


if __name__ == "__main__":
    unittest.main()
