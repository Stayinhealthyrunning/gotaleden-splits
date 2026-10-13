"""Synthetic-only checks for the public-source privacy risk detector."""
import gzip
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_tracked_source_privacy import scan_sqlite  # noqa: E402
from privacy import name_fingerprint  # noqa: E402


class TrackedSourcePrivacyTests(unittest.TestCase):
    def test_protected_name_reverse_format_and_age(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "source.sqlite"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE results(name TEXT, age INTEGER, raw_json TEXT)")
                conn.execute(
                    "INSERT INTO results VALUES (?, ?, ?)",
                    ("Example, Runner", 17, json.dumps({"name": "Example, Runner"})),
                )
                conn.execute(
                    "INSERT INTO results VALUES (?, ?, ?)",
                    ("Unrelated Person", 30, None),
                )
            names, matches, minors = scan_sqlite(db, {name_fingerprint("Runner Example")})
            self.assertEqual((names, matches, minors), (2, 1, 1))
            compressed = Path(temp) / "source.sqlite.gz"
            with db.open("rb") as source, gzip.open(compressed, "wb") as out:
                out.write(source.read())
            self.assertEqual(scan_sqlite(compressed, {name_fingerprint("Runner Example")}), (2, 1, 1))

    def test_nested_relay_identity_and_clean_source(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "teams.sqlite"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE relay(raw_json TEXT)")
                conn.execute(
                    "INSERT INTO relay VALUES (?)",
                    (json.dumps({"team_members": [{"first_name": "Example", "last_name": "Athlete"}]}),),
                )
            self.assertEqual(scan_sqlite(db, {name_fingerprint("Example Athlete")}), (1, 1, 0))
            self.assertEqual(scan_sqlite(db, {name_fingerprint("Different Athlete")}), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
