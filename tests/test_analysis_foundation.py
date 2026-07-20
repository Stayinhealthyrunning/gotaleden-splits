import json
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AnalysisFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        cls.snapshot = json.loads(
            (ROOT / "data/source/eqtiming/api/event-77906-contestants.json").read_text(encoding="utf-8")
        )

    def test_public_snapshot_is_complete_and_race_validated(self):
        self.assertEqual(self.snapshot["event_id"], 77906)
        self.assertEqual(self.snapshot["response_count"], 607)
        self.assertTrue(self.snapshot["passes_included"])
        self.assertEqual(len(self.snapshot["contestants"]), 607)

    def test_nolhaga_is_timing_point_not_relay_exchange(self):
        for race_key, checkpoints in self.data["checkpoints"].items():
            nolhaga = next(item for item in checkpoints if item["key"] == "nolhaga")
            self.assertTrue(nolhaga["is_timing_point"], race_key)
            self.assertFalse(nolhaga["is_relay_exchange"], race_key)
            self.assertEqual(checkpoints[-1]["key"], "alingsas")

    def test_known_individual_has_all_official_passages(self):
        splits = [s for s in self.data["splits"] if s["race_key"] == "individual-75-2026" and s["bib"] == "717"]
        self.assertEqual(len(splits), 10)
        self.assertEqual({s["checkpoint"] for s in splits}, {
            "skatas", "kasjon", "jonsered", "lerum", "floda", "tollered",
            "norsesund", "vastra_bodarna", "nolhaga", "alingsas",
        })
        self.assertEqual(next(s for s in splits if s["checkpoint"] == "nolhaga")["elapsed_seconds"], 19393.64)

    def test_known_relay_has_team_passages_without_public_leg_mapping(self):
        splits = [s for s in self.data["splits"] if s["race_key"] == "relay-75-2026" and s["bib"] == "41"]
        team = next(item for item in self.data["teams"] if item["race_key"] == "relay-75-2026" and item["bib"] == "41")
        self.assertEqual(len(splits), 10)
        self.assertEqual(len(team["team_members"]), 9)
        self.assertNotIn("relay_leg_assignments", self.data)

    def test_web_payload_is_compact_and_raw_sources_stay_in_sqlite(self):
        records = [record for race in self.data["races"].values() for record in race["records"]]
        self.assertFalse(any("raw" in record for record in records))
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as conn:
            raw = json.loads(conn.execute("SELECT raw_json FROM results WHERE bib='717'").fetchone()[0])
            official_split_count = conn.execute("SELECT COUNT(1) FROM splits WHERE is_finish_only_export=0").fetchone()[0]
        self.assertIn("public_contestant_api", raw)
        self.assertEqual(official_split_count, len(self.data["splits"]))
        self.assertTrue(all(split["elapsed_seconds"] > 0 for split in self.data["splits"]))

    def test_static_site_references_existing_analysis_assets(self):
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        for asset in ("data-index.js", "charts.js", "replay.js", "app.js", "style.css"):
            self.assertIn(asset, html)
            self.assertTrue((ROOT / "docs/assets" / asset).is_file())
        self.assertIn("individual-75-2026", html)
        self.assertIn("relay-35-2026", html)
        self.assertTrue((ROOT / "docs/data/route-elevation-2026.json").is_file())


if __name__ == "__main__":
    unittest.main()
