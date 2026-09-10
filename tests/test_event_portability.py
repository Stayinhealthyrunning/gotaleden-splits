import copy
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

    def test_alternate_duo_is_a_team_without_relay_or_finish_key_assumptions(self):
        result = self.run_node(r"""
const duo=adapter.race('duo-long-a'),first=adapter.record('duo-long-a:1'),second=adapter.record('duo-long-a:2'),head=adapter.headToHeadAnalysis(duo,first,second);
const duoUi=window.GRaceUI.race(duo,eventUi);console.log(JSON.stringify({isTeam:duo.isTeam,isRelay:duo.isRelay,format:duo.competitionFormat,field:adapter.referenceProfiles(first).field.label,classReference:adapter.referenceProfiles(first).class.label,finish:head.checkpoints.at(-1).checkpoint,finishName:head.checkpoints.at(-1).name,place:head.checkpoints.at(-1).placeA,sourceUrl:duoUi.sourceUrl}));
""")
        self.assertTrue(result["isTeam"])
        self.assertFalse(result["isRelay"])
        self.assertEqual(result["format"], "duo")
        self.assertEqual(result["field"], "All duos")
        self.assertEqual(result["classReference"], "My division")
        self.assertEqual(result["finishName"], "Harbor Light")
        self.assertEqual(result["place"], 1)
        self.assertEqual(result["sourceUrl"], "https://example.test/coast/results")

    def test_production_contract_accepts_another_event_with_four_families_and_duo(self):
        config = copy.deepcopy(self.config)
        config["event"].update({"event_key": "coast-trail-lab", "name": "Coast Trail Lab", "product_title": "Coast Trail Explorer", "storage_namespace": "coast-lab"})
        config["competition_profiles"]["duo"] = {
            "participant": {"entity": "team", "singular": "duo", "plural": "duos", "profile_label": "DUO ANALYSIS", "possessive": "Duo's"},
            "ui_labels": {"navigation": "Duos", "saved": "Saved duos", "lookup_title": "Open a duo", "lookup_copy": "Search duos.", "class": "Division", "group_analysis": "Divisions", "age_analysis": "Division analysis", "map_single": "DUO MAP", "field": "All duos", "field_analysis": "Entire duo field", "class_reference": "My division", "class_place": "Division place", "class_places": "division places", "class_analysis_eyebrow": "DUO DIVISIONS", "class_analysis_title": "Duos by division", "class_analysis_copy": "Compare divisions.", "class_analysis_retention": "100 = division pace", "members": "Duo members", "entity_heading": "DUO"},
            "competition": {"format": "duo", "team_structure": {"kind": "sequential", "leg_count": 2, "member_assignment": "unknown"}},
            "capabilities": {"goal_pace": False, "sex_filter": False, "age_analysis": False, "club_analysis": False, "person_history": False, "team_members": True, "class_analysis": True, "segment_analysis": True, "replay": True, "head_to_head": True},
        }
        base = copy.deepcopy(config["races"][0])
        races = []
        for key, family, profile in (("coast-long", "long-solo", "individual"), ("coast-mid", "mid-solo", "individual"), ("coast-short", "short-solo", "individual"), ("coast-duo", "duo-long", "duo")):
            race = copy.deepcopy(base)
            race.update({"race_key": key, "race_family": family, "competition_profile": profile, "type": "team" if profile == "duo" else "individual", "section": key, "year": 2032})
            races.append(race)
        config["races"] = races
        catalog = race_catalog(config)
        self.assertEqual({race["race_family"] for race in catalog}, {"long-solo", "mid-solo", "short-solo", "duo-long"})
        duo = next(race for race in catalog if race["race_key"] == "coast-duo")
        contract = race_contract(config, duo)
        self.assertEqual(contract["participant"]["entity"], "team")
        self.assertEqual(contract["competition"]["format"], "duo")
        self.assertEqual(contract["competition"]["team_structure"], {"kind": "sequential", "leg_count": 2, "member_assignment": "unknown"})

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
        for value in ("Gotaleden", "Göteborg", "Floda", "Alingsås", "Nolhaga", "Skatås", "Tollered", "EQ Timing", "route-35", "Coast Trail Lab", "long-solo-a", "62 km", "alingsas", "floda", "gothenburg", "skatas", "nolhaga", "tollered", "Publicerad lagtid", "Lagklass", "Lagmedlemmar", "stafettfältet", "stafettens officiella", "OFFICIELLA STAFETTKLASSER", "Mixed tävling", "Mixed fri", "deltagare/lag", "deltagare eller lag"):
            self.assertNotIn(value.casefold(), source.casefold())
        self.assertNotRegex(source, r"(?:race|key|distance).{0,30}(?:includes|===).{0,12}(?:2026|35|75)")
        central_ui = "\n".join((ROOT / "docs/assets" / name).read_text(encoding="utf-8") for name in ("race-ui.js", "app.js", "favorites.js", "goal-pace.js", "personal-summary.js", "map-page.js"))
        self.assertNotIn("isRelay", central_ui)
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertNotIn("live.eqtiming.com", html)


if __name__ == "__main__":
    unittest.main()
