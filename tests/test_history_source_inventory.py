import collections
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistorySourceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (ROOT / "reports/gotaleden-history-source-inventory.json").read_text(encoding="utf-8")
        )
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        cls.web = json.loads((ROOT / "docs/data/results.json").read_text(encoding="utf-8"))

    def test_inventory_records_premiere_boundary_without_fabricating_an_edition(self):
        inventory = self.inventory
        self.assertEqual(inventory["event_key"], self.config["event"]["event_key"])
        self.assertEqual(inventory["edition_inventory"]["available_data_years"], [2026])
        self.assertEqual(inventory["edition_inventory"]["pre_2026_race_editions"], [])

        future = inventory["edition_inventory"]["future_announcements"]
        self.assertEqual(len(future), 1)
        self.assertEqual(future[0]["year"], 2027)
        self.assertFalse(future[0]["eligible_for_import"])
        self.assertNotIn(2027, {race["year"] for race in self.config["races"]})

    def test_inventory_matches_canonical_config_and_web_export(self):
        expected = {
            item["race_key"]: (item["result_count"], item["split_count"])
            for item in self.inventory["canonical_2026"]["race_editions"]
        }
        config_races = {
            race["race_key"]: race
            for race in self.config["races"]
            if race["data_status"] == "available"
        }
        web_result_counts = {
            race_key: len(race["records"])
            for race_key, race in self.web["races"].items()
        }
        web_split_counts = collections.Counter(
            split["race_key"] for split in self.web["splits"]
        )
        web_checkpoint_keys = {}
        for split in self.web["splits"]:
            checkpoints = web_checkpoint_keys.setdefault(split["race_key"], [])
            if split["checkpoint"] not in checkpoints:
                checkpoints.append(split["checkpoint"])
        source_event = self.config["source_events"]["eqtiming-gotaleden-2026"]

        self.assertEqual(set(expected), set(config_races))
        self.assertEqual(set(expected), set(self.web["races"]))
        self.assertEqual(sum(item[0] for item in expected.values()), 607)
        self.assertEqual(sum(item[1] for item in expected.values()), 4059)
        for race_key, (result_count, split_count) in expected.items():
            race_config = config_races[race_key]
            inventory_race = next(
                item
                for item in self.inventory["canonical_2026"]["race_editions"]
                if item["race_key"] == race_key
            )
            self.assertEqual(race_config["year"], 2026)
            self.assertEqual(race_config["course_version"], "course-v1")
            self.assertEqual(web_result_counts[race_key], result_count)
            self.assertEqual(web_split_counts[race_key], split_count)
            self.assertEqual(
                inventory_race["status_counts"],
                dict(collections.Counter(record["status"] for record in self.web["races"][race_key]["records"])),
            )
            self.assertEqual(inventory_race["normalized_checkpoint_keys"], web_checkpoint_keys[race_key])
            self.assertEqual(inventory_race["participant_entity"], self.web["races"][race_key]["participant"]["entity"])
            binding = source_event["race_bindings"][race_config["source_binding"]["race"]]
            self.assertEqual(inventory_race["published_race_name"], binding["source_race_name"])

        course = self.config["course_versions"]["course-v1"]
        canonical = self.inventory["canonical_2026"]
        self.assertEqual(canonical["course_fingerprint"], course["expected_fingerprint"])
        self.assertEqual(canonical["result_count"], 607)
        self.assertEqual(canonical["split_count"], 4059)
        source_material = canonical["source_material"]
        self.assertEqual(source_material["provider"], source_event["provider"])
        self.assertEqual(source_material["results_url"], source_event["results_url"])
        self.assertTrue((ROOT / source_material["public_snapshot"]).is_file())
        self.assertTrue((ROOT / source_material["build_adapter"]).is_file())

    def test_inventory_has_attributable_sources_and_explicit_non_import_decisions(self):
        sources = self.inventory["sources"]
        self.assertGreaterEqual(len(sources), 5)
        self.assertTrue(all(source["url"].startswith("https://") for source in sources))
        self.assertTrue(all(source["evidence"].strip() for source in sources))
        self.assertIn("https://live.eqtiming.com/77906", {source["url"] for source in sources})

        decisions = {
            item["period"]: item for item in self.inventory["non_import_decisions"]
        }
        self.assertEqual(decisions["before 2026"]["decision"], "not_applicable")
        self.assertEqual(decisions["2027"]["decision"], "not_imported")
        self.assertIn("future", decisions["2027"]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
