import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from source_bindings import race_catalog, race_contract  # noqa: E402


class EventPortabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        cls.node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")

    def run_node(self, body):
        if not self.node:
            self.skipTest("Node.js is required")
        script = """
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['tests/fixtures/alternate-event.js','docs/assets/race-ui.js','docs/assets/data-adapter.js','docs/assets/goal-pace.js','docs/assets/favorites.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'));
const fixture=window.GAlternateEventFixture.create(),bundles={};
for(const [key,entry] of Object.entries(fixture.data.courses))bundles[key]={route:fixture.assets[entry.assets.route],elevation:fixture.assets[entry.assets.elevation]};
const adapter=window.GDataAdapter.create(fixture.data,bundles),eventUi=window.GRaceUI.event(fixture.data);
""" + body
        result = subprocess.run([self.node, "-e", script], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_real_catalog_has_explicit_event_entity_competition_and_capabilities(self):
        event = self.config["event"]
        self.assertEqual(event["storage_namespace"], "gotaleden")
        self.assertTrue(event["product_title"])
        races = race_catalog(self.config)
        self.assertEqual(len(races), 4)
        for race in races:
            contract = race_contract(self.config, race)
            self.assertIn(contract["participant"]["entity"], {"person", "team"})
            self.assertTrue(contract["competition"]["format"])
            self.assertIn("goal_pace", contract["capabilities"])
            self.assertTrue(contract["presentation"]["distance_label"])

    def test_alternate_event_duo_class_and_capability_contract(self):
        result = self.run_node(r"""
const duo=adapter.race('duo-long-a'),solo=adapter.race('long-solo-b'),team=adapter.team('duo-long-a:1');
const ranked=adapter.relayClassMeta(adapter.record('duo-long-a:1')),unranked=adapter.relayClassMeta(adapter.record('duo-long-a:2')),unknown=adapter.relayClassMeta(adapter.record('duo-long-a:6'));
console.log(JSON.stringify({event:eventUi.productTitle,families:new Set([...adapter.races.values()].map(r=>r.family)).size,duo:{entity:duo.participantEntity,format:duo.competitionFormat,structure:duo.teamStructure,members:team.team_members.length,goal:duo.capabilities.goal_pace,course:duo.courseVersion},solo:{course:solo.courseVersion,goal:solo.capabilities.goal_pace},classes:{ranked,unranked,unknown}}));
""")
        self.assertEqual(result["event"], "Coast Trail Explorer")
        self.assertEqual(result["families"], 4)
        self.assertEqual(result["duo"]["entity"], "team")
        self.assertEqual(result["duo"]["format"], "duo")
        self.assertEqual(result["duo"]["structure"], {"kind": "sequential", "leg_count": 2, "member_assignment": "unknown"})
        self.assertEqual(result["duo"]["members"], 2)
        self.assertFalse(result["duo"]["goal"])
        self.assertTrue(result["solo"]["goal"])
        self.assertEqual(result["duo"]["course"], result["solo"]["course"])
        self.assertTrue(result["classes"]["ranked"]["ranked"])
        self.assertFalse(result["classes"]["unranked"]["ranked"])
        self.assertTrue(result["classes"]["unknown"]["id"].startswith("other-"))

    def test_storage_is_event_scoped_and_legacy_favorites_migrate(self):
        result = self.run_node(r"""
const values=new Map([['legacy-favorites','["same-race:1"]']]),storage={getItem:key=>values.has(key)?values.get(key):null,setItem:(key,value)=>values.set(key,value)};
const migrated=window.GFavorites.create({storage,key:'event-a:favorites',legacyKeys:['legacy-favorites']});
const isolated=window.GFavorites.create({storage,key:'event-b:favorites'});isolated.add('same-race:1');migrated.remove('same-race:1');
console.log(JSON.stringify({a:migrated.all(),b:isolated.all(),saved:values.get('event-a:favorites'),race:eventUi.storageKey('race'),goal:eventUi.storageKey('goal-pace'),event:eventUi.eventName('goal-pace')}));
""")
        self.assertEqual(result["a"], [])
        self.assertEqual(result["b"], ["same-race:1"])
        self.assertEqual(json.loads(result["saved"]), [])
        self.assertTrue(result["race"].startswith("coast-lab:"))
        self.assertTrue(result["goal"].startswith("coast-lab:"))
        self.assertTrue(result["event"].startswith("coast-lab:"))

    def test_generic_runtime_hardcoding_and_is_relay_gate(self):
        core = [
            "race-ui.js", "app.js", "data-adapter.js", "favorites.js", "goal-pace.js",
            "personal-summary.js", "charts.js", "course-difficulty.js", "head-to-head.js",
            "history-engine.js", "history-ui.js", "map-engine.js", "map-page.js", "map-duel.js",
            "runner-replay.js", "profile-journey.js", "interactive-analysis.js",
        ]
        source = "\n".join((ROOT / "docs/assets" / name).read_text(encoding="utf-8") for name in core)
        for value in ("Gotaleden", "Göteborg", "Floda", "Alingsås", "Nolhaga", "Skatås", "Tollered", "EQ Timing", "route-35", "Coast Trail Lab", "long-solo-a", "62 km"):
            self.assertNotIn(value.casefold(), source.casefold())
        self.assertNotRegex(source, r"(?:race|key|distance).{0,30}(?:includes|===).{0,12}(?:2026|35|75)")
        central_ui = "\n".join((ROOT / "docs/assets" / name).read_text(encoding="utf-8") for name in ("race-ui.js", "app.js", "favorites.js", "goal-pace.js", "personal-summary.js", "map-page.js"))
        self.assertNotIn("isRelay", central_ui)


if __name__ == "__main__":
    unittest.main()
