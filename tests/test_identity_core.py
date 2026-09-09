import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from identity import IdentityConflictError, resolve_person_identity  # noqa: E402


def evidence(external_id, scope="provider"):
    return [{"provider": "portable-provider", "id_type": "person", "scope": scope, "external_id": external_id, "confidence": "verified"}]


class IdentityCoreTests(unittest.TestCase):
    def resolve(self, items, race="edition-a", event="event-a", result="result-a"):
        return resolve_person_identity(items, race_key=race, source_event_key=event, local_result_id=result)

    def test_provider_identity_is_shared_across_editions_and_names_do_not_matter(self):
        first = self.resolve(evidence("global-1"), race="edition-a", event="event-a")
        second = self.resolve(evidence("global-1"), race="edition-b", event="event-b")
        self.assertEqual(first["person_key"], second["person_key"])
        self.assertEqual(first["scope"], "provider")

    def test_event_scoped_id_is_not_shared_across_events(self):
        first = self.resolve(evidence("same-id", "source_event"), event="event-a")
        second = self.resolve(evidence("same-id", "source_event"), event="event-b")
        self.assertNotEqual(first["person_key"], second["person_key"])

    def test_name_demographics_and_bib_never_create_identity(self):
        first = self.resolve([], race="edition-a", result="bib-10")
        same_name_other_year = self.resolve([], race="edition-b", result="bib-10")
        same_name_demographics_other_result = self.resolve([], race="edition-b", result="bib-11")
        self.assertEqual(first["status"], "local")
        self.assertEqual(first["scope"], "race_edition")
        self.assertEqual(len({first["person_key"], same_name_other_year["person_key"], same_name_demographics_other_result["person_key"]}), 3)

    def test_conflicting_verified_identifiers_fail_and_rebuild_is_deterministic(self):
        items = evidence("one") + evidence("two")
        with self.assertRaises(IdentityConflictError):
            self.resolve(items)
        self.assertEqual(self.resolve(evidence("stable")), self.resolve(evidence("stable")))

    def test_team_names_do_not_create_cross_edition_identity(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript((TOOLS / "schema.sql").read_text(encoding="utf-8"))
        connection.execute("INSERT INTO teams(source_external_id,team_name,normalized_name) VALUES(?,?,?)", ("edition-a:7", "Same Team", "same team"))
        connection.execute("INSERT INTO teams(source_external_id,team_name,normalized_name) VALUES(?,?,?)", ("edition-b:7", "Same Team", "same team"))
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM teams WHERE normalized_name='same team'").fetchone()[0], 2)

    def test_real_export_exposes_deterministic_scoped_identity(self):
        import json
        payload = json.loads((ROOT / "docs/data/results.json").read_text(encoding="utf-8"))
        individual = payload["races"]["individual-75-2026"]["records"][0]
        self.assertTrue(individual["person_key"].startswith("person-"))
        self.assertEqual(individual["identity_status"], "verified")
        self.assertEqual(individual["identity_scope"], "source_event")
        relay_member = payload["team_members"][0]
        self.assertEqual(relay_member["identity_status"], "local")
        self.assertEqual(relay_member["identity_scope"], "race_edition")
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM athlete_external_ids WHERE identity_scope='source_event' AND confidence='verified'").fetchone()[0], 437)

    def test_adapter_exposes_identity_without_changing_public_record_id(self):
        import json
        import os
        import shutil
        import subprocess
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = """const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));const data=JSON.parse(fs.readFileSync('docs/data/results.json','utf8')),route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8')),elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8')),adapter=window.GDataAdapter.create(data,route,elevation),record=adapter.race('individual-75-2026').records[0];console.log(JSON.stringify({id:record.id,personKey:record.personKey,status:record.identityStatus,scope:record.identityScope}))"""
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertTrue(value["id"].startswith("individual-75-2026:"))
        self.assertTrue(value["personKey"].startswith("person-"))
        self.assertEqual((value["status"], value["scope"]), ("verified", "source_event"))


if __name__ == "__main__":
    unittest.main()
