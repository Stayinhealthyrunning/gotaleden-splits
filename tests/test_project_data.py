import hashlib
import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from eqtiming_official_import import build_relay_assignments  # noqa: E402


EXPECTED_SOURCE_HASHES = {
    "individual-35-2026.csv": "45609cee0f81db62c7f76e1e26bf58c78bcb1cdd3759d8c91136feacaa579ed3",
    "individual-75-2026.csv": "2fce8821fcbdd01811f2803a753ffb7e44aec392a46871bdd9ff26e758bec3da",
    "relay-35-2026.csv": "6454d958bd3ef08b3d47e8c07dbe14de79932a1f696f5a6e54bb35d5926f4367",
    "relay-75-2026.csv": "6751c690a56a387080af9a3ea16e7334df8f7ea5fba75633891124d240adca1d",
    "Resultlist-77906-20260719155309.csv": "8ace0716c45bd67827854438d70820f96307aafe3b0b3518618dde515ab66487",
    "Resultlist-77906-20260719155432.txt": "88d04c4e76b33fe269660102f832a97c23673b0d11cfd5da153aab11fcb14fca",
    "Resultlist-77906-20260719155433.csv": "8ace0716c45bd67827854438d70820f96307aafe3b0b3518618dde515ab66487",
    "Resultlist-77906-20260719155434.csv": "0d899e39c353bed5146a756a3e2af244b7143c8841c7ead1b2a0a304a1bdf29f",
    "Resultlist-77906-20260719155435.csv": "2738b39ccdb5197834cbe0e3bae47a02361ba592c97e025e705548bd2d0bfefb",
    "Startlist-77906-20260719155427.xml": "98350761026b4adc7ef45e2a690727c76dc5b82785ef43e9bfe9f655d0167ef7",
    "Startlist-77906-20260719155429.csv": "9b7b7d91430e0940bd297c2be78c4a7bb5e2db336e5c480e3b16b2e9056f561b",
    "Startlist-77906-20260719155430.csv": "c5c9c76faf0d81ff2f8b588ac2b749ee1e3adb7d4f7c38f40c7935053bc31daa",
}


class ProjectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        cls.route = json.loads((ROOT / "docs/data/route.json").read_text(encoding="utf-8"))
        cls.report = json.loads((ROOT / "reports/import-summary-2026.json").read_text(encoding="utf-8"))
        cls.relay_report = json.loads((ROOT / "reports/relay-member-import-report.json").read_text(encoding="utf-8"))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(ROOT / "data/gotaleden.sqlite")
        try:
            yield conn
        finally:
            conn.close()

    def test_four_races_and_base_counts(self):
        expected = {
            "individual-75-2026": 274,
            "individual-35-2026": 163,
            "relay-75-2026": 121,
            "relay-35-2026": 49,
        }
        self.assertEqual(set(self.results["races"]), set(expected))
        self.assertEqual(sum(expected.values()), 607)
        for key, count in expected.items():
            self.assertEqual(len(self.results["races"][key]["records"]), count)

    def test_expected_status_counts(self):
        expected = {
            "individual-75-2026": {"FINISHED": 206, "DNF": 13, "DNS": 55},
            "individual-35-2026": {"FINISHED": 127, "DNF": 2, "DNS": 34},
            "relay-75-2026": {"FINISHED": 109, "DNF": 1, "DNS": 11},
            "relay-35-2026": {"FINISHED": 45, "DNF": 1, "DNS": 3},
        }
        for race_key, statuses in expected.items():
            self.assertEqual(self.report["races"][race_key]["statuses"], statuses)

    def test_no_result_duplicates(self):
        with self.connect() as conn:
            total, distinct = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT race_id || ':' || source_result_id) FROM results"
            ).fetchone()
        self.assertEqual((total, distinct), (607, 607))

    def test_individuals_and_teams_are_separate(self):
        with self.connect() as conn:
            invalid = conn.execute(
                """SELECT COUNT(*) FROM results
                   WHERE (entity_type='athlete' AND (athlete_id IS NULL OR team_id IS NOT NULL))
                      OR (entity_type='team' AND (team_id IS NULL OR athlete_id IS NOT NULL))"""
            ).fetchone()[0]
        self.assertEqual(invalid, 0)

    def test_leg_ranges_are_race_specific(self):
        with self.connect() as conn:
            ranges = {row[0]: (row[1], row[2]) for row in conn.execute(
                """SELECT races.race_key, MIN(a.leg_no), MAX(a.leg_no)
                   FROM relay_leg_assignments a JOIN results r ON r.id=a.result_id
                   JOIN races ON races.id=r.race_id GROUP BY races.race_key"""
            ).fetchall()}
        self.assertEqual(ranges["relay-75-2026"], (1, 9))
        self.assertEqual(ranges["relay-35-2026"], (1, 4))

    def test_known_xml_codes_map_to_correct_legs(self):
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT races.race_key,r.bib,a.leg_no,a.source_start_number,a.runner_name_as_published,a.assignment_status
                   FROM relay_leg_assignments a JOIN results r ON r.id=a.result_id
                   JOIN races ON races.id=r.race_id
                   WHERE (races.race_key='relay-75-2026' AND r.bib='78' AND a.leg_no=3)
                      OR (races.race_key='relay-35-2026' AND r.bib='1020' AND a.leg_no=1)
                   ORDER BY races.race_key"""
            ).fetchall()
        self.assertIn(("relay-75-2026", "78", 3, "3078", "Erika Sjögren", "verified_xml_and_result_list"), rows)
        self.assertIn(("relay-35-2026", "1020", 1, "2020", "Amanda Jinnemark", "verified_xml_and_result_list"), rows)

    def test_start_time_disambiguates_numeric_code_collisions(self):
        for race in self.relay_report["races"].values():
            verification = race["code_pattern_verification"]
            self.assertTrue(verification["verified"])
            self.assertTrue(verification["start_time_is_part_of_identity"])
            self.assertGreater(verification["same_numeric_codes_in_other_start_times_count"], 0)

    def test_same_runner_can_run_multiple_legs(self):
        with self.connect() as conn:
            repeated = conn.execute(
                """SELECT COUNT(*) FROM (
                     SELECT result_id,athlete_id FROM relay_leg_assignments
                     WHERE athlete_id IS NOT NULL GROUP BY result_id,athlete_id HAVING COUNT(*)>1
                   )"""
            ).fetchone()[0]
        self.assertGreater(repeated, 0)

    def test_missing_and_conflict_assignments_never_have_athletes(self):
        with self.connect() as conn:
            invalid = conn.execute(
                "SELECT COUNT(*) FROM relay_leg_assignments WHERE assignment_status IN ('missing','conflict') AND athlete_id IS NOT NULL"
            ).fetchone()[0]
            blank_athletes = conn.execute("SELECT COUNT(*) FROM athletes WHERE TRIM(canonical_name)='' ").fetchone()[0]
        self.assertEqual(invalid, 0)
        self.assertEqual(blank_athletes, 0)

    def test_synthetic_conflict_is_not_verified(self):
        teams = [{"Startnumber": "78", "Firstname": "Team", "Surname": "(Wrong Runner)"}]
        xml = [{"startno": "1078", "starttid": "08:00:00", "fornavn": "Right", "etternavn": "Runner"}]
        assignments, _ = build_relay_assignments("relay-75-2026", teams, xml)
        self.assertEqual(assignments[0]["assignment_status"], "conflict")
        self.assertIsNone(assignments[0]["runner_name"])

    def test_all_original_fields_are_preserved(self):
        with self.connect() as conn:
            raw = json.loads(conn.execute("SELECT raw_json FROM results WHERE bib='717'").fetchone()[0])
        self.assertEqual(len(raw["legacy_finish_export"]["row"]), 81)
        self.assertIn("_unlabelled_22", raw["primary_result_file"]["row"])
        self.assertIn("Resultlist-77906-20260719155309.csv", raw["cross_validation"])

    def test_csv_files_are_finish_only_but_public_snapshot_has_splits(self):
        self.assertTrue(self.results["meta"]["intermediate_splits_available"])
        self.assertGreater(len(self.results["splits"]), 3000)
        for race in self.report["races"].values():
            self.assertEqual(race["point_names"], ["Mål"])
            self.assertEqual(race["intermediate_split_rows_in_csv"], 0)
            self.assertGreater(race["public_api_split_rows"], 0)

    def test_all_source_files_are_byte_unchanged(self):
        source_dir = ROOT / "data/source/eqtiming"
        self.assertEqual({path.name for path in source_dir.iterdir() if path.is_file()}, set(EXPECTED_SOURCE_HASHES))
        for file_name, expected in EXPECTED_SOURCE_HASHES.items():
            actual = hashlib.sha256((source_dir / file_name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, file_name)

    def test_route_and_floda_slice(self):
        self.assertGreater(self.route["full_distance_km"], 76.0)
        self.assertLess(self.route["full_distance_km"], 79.0)
        self.assertLess(self.route["floda_start"]["distance_from_requested_m"], 10.0)
        self.assertGreater(self.route["floda_start"]["remaining_distance_km"], 34.0)
        self.assertLess(self.route["floda_start"]["remaining_distance_km"], 38.0)

    def test_rebuild_is_idempotent(self):
        command = [sys.executable, str(ROOT / "tools/build_project_data.py")]
        subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with self.connect() as conn:
            first = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in
                          ("results", "teams", "team_members", "relay_leg_assignments"))
        subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with self.connect() as conn:
            second = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in
                           ("results", "teams", "team_members", "relay_leg_assignments"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
