import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from gpx_analysis import build_elevation_profile, parse_gpx  # noqa: E402


class GpxAndNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        cls.route = json.loads((ROOT / "docs/data/route.json").read_text(encoding="utf-8"))
        cls.profile = json.loads((ROOT / "docs/data/route-elevation-2026.json").read_text(encoding="utf-8"))
        cls.gpx_report = json.loads((ROOT / "reports/gpx-comparison.json").read_text(encoding="utf-8"))
        cls.coverage = json.loads((ROOT / "reports/eqtiming-split-coverage.json").read_text(encoding="utf-8"))

    def test_result_and_positive_passage_counts(self):
        records = [record for race in self.data["races"].values() for record in race["records"]]
        self.assertEqual(len(records), 607)
        self.assertEqual(len(self.data["splits"]), 4059)
        self.assertTrue(all(split["elapsed_seconds"] > 0 for split in self.data["splits"]))
        self.assertEqual(
            {key: value["imported_passages"] for key, value in self.coverage["races"].items()},
            {"individual-75-2026": 2121, "individual-35-2026": 638, "relay-75-2026": 1077, "relay-35-2026": 223},
        )

    def test_known_split_has_explicit_split_and_cumulative_fields(self):
        split = next(item for item in self.data["splits"] if item["race_key"] == "individual-75-2026" and item["bib"] == "717" and item["checkpoint"] == "skatas")
        self.assertEqual(split["split_place_overall"], 1)
        self.assertAlmostEqual(split["split_speed_kmh"], 15.43)
        self.assertAlmostEqual(split["split_pace_min_per_km"], 3.889)
        self.assertAlmostEqual(split["cumulative_speed_kmh"], 15.43)
        self.assertAlmostEqual(split["cumulative_pace_min_per_km"], 3.889)
        self.assertEqual(split["source_station_uid"], "1457937")

    def test_participant_age_birth_year_club_fallback_and_ranked_class(self):
        anton = next(item for item in self.data["races"]["individual-75-2026"]["records"] if item["bib"] == "717")
        self.assertEqual((anton["age"], anton["birth_year"]), (34, 1992))
        self.assertTrue(anton["public_contestant_uid"])
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as conn:
            rows = conn.execute("SELECT club,raw_json FROM results WHERE club IS NOT NULL").fetchall()
        fallbacks = []
        for club, raw_text in rows:
            raw = json.loads(raw_text)
            primary = raw["primary_result_file"]["row"].get("Club")
            public = raw["public_contestant_api"]["row"]
            public_club = public.get("Klubbnavn") or (public.get("Utover") or {}).get("Klubbnavn")
            if not primary and public_club:
                fallbacks.append((club, public_club))
        self.assertTrue(fallbacks)
        self.assertTrue(all(actual.strip() == expected.strip() for actual, expected in fallbacks))
        mixed = next(item for item in self.data["races"]["relay-75-2026"]["records"] if item["class_name"] == "Mixed ej tävling - Fri fördelning")
        self.assertTrue(mixed["class_is_ranked"])
        self.assertEqual(mixed["class_competition_type"], "non_competitive")

    def test_route_distance_mapping_and_replay_anchors(self):
        long = {item["key"]: item for item in self.data["checkpoints"]["individual-75-2026"]}
        short = {item["key"]: item for item in self.data["checkpoints"]["individual-35-2026"]}
        self.assertEqual(long["gothenburg"]["route_distance_km"], 0)
        self.assertAlmostEqual(long["alingsas"]["route_distance_km"], self.route["full_distance_km"], places=4)
        self.assertAlmostEqual(short["floda"]["route_distance_km"], self.route["floda_start"]["cumulative_km_from_gothenburg"], places=4)
        self.assertEqual(short["floda"]["race_distance_km"], 0)
        self.assertEqual(short["floda"]["route_distance_km"], long["floda"]["route_distance_km"])
        self.assertLess(long["nolhaga"]["route_distance_km"], long["alingsas"]["route_distance_km"])
        self.assertGreater(long["alingsas"]["route_distance_km"] - long["nolhaga"]["route_distance_km"], 0.1)

    def test_official_gpx_is_master_and_reference_does_not_replace_geometry(self):
        official = parse_gpx(ROOT / "data/source/gpx/Gotaleden_Ultra_75km-30april.gpx")
        self.assertEqual(self.route["point_count"], len(official["points"]))
        self.assertEqual(self.route["points"][0][:2], [round(official["points"][0]["lat"], 6), round(official["points"][0]["lon"], 6)])
        self.assertEqual(self.route["points"][-1][:2], [round(official["points"][-1]["lat"], 6), round(official["points"][-1]["lon"], 6)])
        self.assertEqual(self.gpx_report["route_master"]["file"], "Gotaleden_Ultra_75km-30april.gpx")
        self.assertGreater(len(self.gpx_report["off_route_sections_over_100m"]), 0)

    def test_elevation_profile_and_missing_reference_fallback(self):
        distances = [point["route_distance_km"] for point in self.profile["points"]]
        self.assertEqual(distances, sorted(distances))
        self.assertAlmostEqual(distances[-1], self.route["full_distance_km"], places=4)
        self.assertTrue(self.profile["meta"]["reference_used"])
        official = parse_gpx(ROOT / "data/source/gpx/Gotaleden_Ultra_75km-30april.gpx")
        fallback, _ = build_elevation_profile(official, None)
        self.assertFalse(fallback["meta"]["reference_used"])
        self.assertEqual(fallback["meta"]["source"], "official GPX elevation")
        self.assertAlmostEqual(fallback["points"][-1]["route_distance_km"], official["points"][-1]["distance_km"], places=4)

    def test_relay_mapping_is_internal_only(self):
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        app = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertNotIn("Etapper och löpare", html + app)
        self.assertNotIn("Verifierade etapper", html + app)
        self.assertNotIn("Fleretappslöpare", html + app)
        self.assertNotIn("relay_leg_assignments", self.data)
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as conn:
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM relay_leg_assignments").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
