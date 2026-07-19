import json
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ProjectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        cls.route = json.loads((ROOT / "docs/data/route.json").read_text(encoding="utf-8"))
        cls.report = json.loads((ROOT / "reports/import-summary-2026.json").read_text(encoding="utf-8"))

    def test_four_races_present(self):
        self.assertEqual(
            set(self.results["races"]),
            {"individual-75-2026", "individual-35-2026", "relay-75-2026", "relay-35-2026"}
        )

    def test_record_counts(self):
        expected = {
            "individual-75-2026": 274,
            "individual-35-2026": 163,
            "relay-75-2026": 121,
            "relay-35-2026": 49,
        }
        for key, count in expected.items():
            self.assertEqual(len(self.results["races"][key]["records"]), count)

    def test_all_original_columns_preserved(self):
        for race in self.report["races"].values():
            self.assertEqual(race["original_column_count"], 81)

    def test_current_csv_is_finish_only(self):
        for race in self.report["races"].values():
            self.assertEqual(race["point_names"], ["Mål"])
            self.assertEqual(race["intermediate_split_rows_in_csv"], 0)

    def test_route_and_floda_slice(self):
        self.assertGreater(self.route["full_distance_km"], 76.0)
        self.assertLess(self.route["full_distance_km"], 79.0)
        self.assertLess(self.route["floda_start"]["distance_from_requested_m"], 10.0)
        self.assertGreater(self.route["floda_start"]["remaining_distance_km"], 34.0)
        self.assertLess(self.route["floda_start"]["remaining_distance_km"], 38.0)

    def test_relay_contact_not_imported_as_leg_assignment(self):
        conn = sqlite3.connect(ROOT / "data/gotaleden.sqlite")
        try:
            count = conn.execute("SELECT COUNT(*) FROM relay_leg_assignments").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_sqlite_result_total(self):
        conn = sqlite3.connect(ROOT / "data/gotaleden.sqlite")
        try:
            count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            self.assertEqual(count, 607)
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
