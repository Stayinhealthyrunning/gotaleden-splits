import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class RelayAnalysisUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (DOCS / "assets/app.js").read_text(encoding="utf-8")
        cls.adapter = (DOCS / "assets/data-adapter.js").read_text(encoding="utf-8")
        cls.interactive = (DOCS / "assets/interactive-analysis.js").read_text(encoding="utf-8")
        cls.replay = (DOCS / "assets/runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (DOCS / "assets/map-duel.js").read_text(encoding="utf-8")
        cls.css = (DOCS / "assets/style.css").read_text(encoding="utf-8")
        cls.data = json.loads((DOCS / "data/results-2026.json").read_text(encoding="utf-8"))

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        completed = subprocess.run([node, "-e", body], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_conflicting_person_sex_never_controls_relay_class(self):
        self.run_node(r"""
global.window={};require('vm').runInThisContext(require('fs').readFileSync('docs/assets/data-adapter.js','utf8'));
const race={section:'x',type:'relay',gpx_distance_km:1,nominal_distance_km:1,records:[
 {bib:'A',name:'Lag A',sex:'M',class_name:'Kvinnor ',class_is_ranked:true,status:'FINISHED',finish_seconds:100},
 {bib:'B',name:'Lag B',sex:'F',class_name:'Män',class_is_ranked:true,status:'FINISHED',finish_seconds:90}]};
const adapter=window.GDataAdapter.create({races:{r:race},checkpoints:{r:[{key:'s',name:'S',route_distance_km:0},{key:'m',name:'Mål',route_distance_km:1}]},splits:[]},{full_distance_km:1,points:[[0,0,0,0],[0,0,0,1]]},{points:[]});
const a=adapter.race('r').records[0],b=adapter.race('r').records[1];
if(adapter.relayClassMeta(a).id!=='women'||adapter.relayClassMeta(b).id!=='men')throw new Error('sex controlled class');
if(adapter.filtered('r',{className:'Kvinnor'}).map(x=>x.bib).join()!=='A')throw new Error('class filter');
if(adapter.relayClassMeta(a).color===adapter.relayClassMeta(b).color)throw new Error('class color');
""")

    def test_relay_75_and_35_class_series_use_all_analytical_segments(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const adapter=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
for(const [key,count] of [['relay-75-2026',9],['relay-35-2026',4]]){const race=adapter.race(key),groups=adapter.relayClassGroups(race.records,race);if(groups.length!==4)throw new Error(key+' groups');for(const group of groups){if(group.stats.length!==count||group.retention.indexValues.length!==count)throw new Error(key+' '+group.id)}}
const race=adapter.race('relay-75-2026'),field=adapter.segmentRanking(race.records,'gothenburg','skatas','relative','field'),own=adapter.segmentRanking(race.records,'gothenburg','skatas','relative','class');if(!field.some(item=>Math.abs(item.relative-own.find(x=>x.record.id===item.record.id).relative)>.0001))throw new Error('class median comparison not distinct');
""")

    def test_relay_results_profile_replay_and_duel_contracts(self):
        for text in ("Lagklass", "Klassplats", "Tävlingsstatus", "Analytisk klasspercentil", "Relativt egen klass"):
            self.assertIn(text, self.app)
        self.assertIn("race.isRelay?'':record.club", self.app)
        self.assertIn("race.isRelay?'<tr><th data-sort=\"overall_place\">Total", self.app)
        self.assertIn("Alla lag", self.replay)
        self.assertIn("Min stafettklass", self.replay)
        self.assertIn("record.isRelay&&key==='sex'", self.replay)
        self.assertIn("non-competitive-badge", self.replay)
        self.assertIn("adapter.relayClassMeta(record)", self.duel)
        self.assertIn("color:item.color", self.duel)
        self.assertIn("BASE_PLAYBACK_SECONDS=180", self.duel)

    def test_relay_analysis_features_and_mixed_free_rules_are_wired(self):
        for text in ("renderRelayStatistics", "relayClassAdvancements", "Egen klass", "Hela stafettfältet", "Fartretention per klass"):
            self.assertIn(text, self.interactive + self.app + self.html)
        self.assertIn("group.ranked", self.interactive)
        self.assertIn("Ej tävling", self.interactive + self.app + self.replay + self.duel)
        self.assertIn("filter(item=>relayClassMeta(item).ranked)", self.adapter)
        self.assertIn("[hidden]{display:none!important}", self.css)
        self.assertIn(".analysis-grid>*{min-width:0}", self.css)

    def test_individual_contract_and_data_integrity_remain(self):
        for text in ("Kön", "Genusperspektiv", "Klass & ålder", "Klubb & ort"):
            self.assertIn(text, self.html + self.app)
        for text in ("Hela fältet", "Min klass", "Mitt kön"):
            self.assertIn(text, self.replay)
        self.assertEqual(sum(len(r["records"]) for r in self.data["races"].values()), 607)
        self.assertEqual(len(self.data["splits"]), 4059)
        self.assertEqual({k: len(v["records"]) for k, v in self.data["races"].items()}, {
            "individual-75-2026": 274, "individual-35-2026": 163,
            "relay-75-2026": 121, "relay-35-2026": 49,
        })
        for key, expected in (("individual-75-2026", 9), ("relay-75-2026", 9), ("individual-35-2026", 4), ("relay-35-2026", 4)):
            checkpoints = self.data["checkpoints"][key]
            self.assertEqual(len([cp for cp in checkpoints if cp.get("analysis_boundary", True)]) - 1, expected)
            nolhaga = next(cp for cp in checkpoints if cp["key"] == "nolhaga")
            self.assertTrue(nolhaga["timing_only"])
            self.assertTrue(nolhaga["speaker_checkpoint"])
            self.assertTrue(nolhaga["replay_anchor"])
            self.assertFalse(nolhaga["analysis_boundary"])


if __name__ == "__main__":
    unittest.main()
