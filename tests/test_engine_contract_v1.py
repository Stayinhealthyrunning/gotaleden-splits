import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EngineContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "config/engine-contract-v1.json").read_text(encoding="utf-8"))
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))

    def test_contract_is_frozen_v1(self):
        self.assertEqual(self.contract["contract_id"], "loppanalys-engine-1.0")
        self.assertEqual(self.contract["schema_version"], 1)
        self.assertEqual(self.contract["status"], "frozen")

    def test_event_satisfies_engine_identity_fields(self):
        event = self.config["event"]
        for key in self.contract["payload"]["event_required"]:
            self.assertTrue(event.get(key), key)

    def test_competition_profiles_use_known_entities_and_capabilities(self):
        known = set(self.contract["capabilities"])
        entities = set(self.contract["payload"]["participant_entities"])
        assignments = set(self.contract["payload"]["team_member_assignment"])
        for name, profile in self.config["competition_profiles"].items():
            self.assertIn(profile["participant"]["entity"], entities, name)
            self.assertTrue(profile["competition"]["format"], name)
            structure = profile["competition"]["team_structure"]
            self.assertIn(structure["member_assignment"], assignments, name)
            unknown = set(profile["capabilities"]) - known
            self.assertFalse(unknown, f"{name}: unknown capabilities {sorted(unknown)}")

    def test_every_race_resolves_to_a_profile_and_known_data_status(self):
        profiles = self.config["competition_profiles"]
        statuses = set(self.contract["payload"]["data_status"])
        for race in self.config["races"]:
            self.assertIn(race["competition_profile"], profiles, race["race_key"])
            self.assertIn(race["data_status"], statuses, race["race_key"])
            self.assertTrue(race["race_family"], race["race_key"])
            self.assertTrue(race["course_version"], race["race_key"])

    def test_contract_forbids_identity_and_geometry_shortcuts(self):
        principles = " ".join(self.contract["principles"]).lower()
        identity = " ".join(self.contract["identity"]["rules"]).lower()
        course = " ".join(self.contract["course"]["rules"]).lower()
        replay = self.contract["capabilities"]["replay"].lower()
        self.assertIn("never fabricated", principles)
        self.assertIn("name equality alone", identity)
        self.assertIn("race family is not a course version", course)
        self.assertIn("local route asset", course + " " + replay)


if __name__ == "__main__":
    unittest.main()
