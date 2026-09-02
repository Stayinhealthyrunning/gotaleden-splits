import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class WholeRacePaceBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = (ASSETS / "data-adapter.js").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.interactive = (ASSETS / "interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.results = json.loads(
            (DOCS / "data/results-2026.json").read_text(encoding="utf-8")
        )

    def run_node(self, script):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for adapter integration tests")
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_synthetic_formula_and_complete_finished_cohort(self):
        self.run_node(
            r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const checkpoints=[
  {key:'start',name:'Start',route_distance_km:0,race_distance_km:0},
  {key:'cp1',name:'Kontroll',route_distance_km:4,race_distance_km:4},
  {key:'nolhaga',name:'Nolhaga',route_distance_km:5,race_distance_km:5,analysis_boundary:false,timing_only:true},
  {key:'finish',name:'Mål',route_distance_km:10,race_distance_km:10}
];
const records=[
  {bib:'A',status:'FINISHED',finish_seconds:1000},
  {bib:'B',status:'FINISHED',finish_seconds:2000},
  {bib:'DNF',status:'DNF',finish_seconds:3000},
  {bib:'MISSING',status:'FINISHED',finish_seconds:1500}
];
const splits=[];
for(const [bib,cp1,finish] of [['A',200,1000],['B',1200,2000],['DNF',400,3000]]){
  splits.push({race_key:'test',bib,checkpoint:'cp1',elapsed_seconds:cp1});
  splits.push({race_key:'test',bib,checkpoint:'finish',elapsed_seconds:finish});
}
splits.push({race_key:'test',bib:'MISSING',checkpoint:'finish',elapsed_seconds:1500});
const data={races:{test:{section:'Test',type:'individual',gpx_distance_km:10,nominal_distance_km:10,records}},checkpoints:{test:checkpoints},splits};
const adapter=window.GDataAdapter.create(data,{full_distance_km:10,points:[[0,0,0,0],[0,0,0,10]]},{});
const result=adapter.wholeRacePaceProfile(adapter.race('test').records,'test');
const close=(actual,expected)=>Math.abs(actual-expected)<1e-9;
if(result.count!==2||result.cohort.map(item=>item.bib).join(',')!=='A,B')throw new Error('cohort');
if(!close(result.overallPaces[0],100)||!close(result.overallPaces[1],200))throw new Error('full-race paces');
if(!close(result.baselinePace,150))throw new Error('baseline median');
if(!close(result.segmentMedianPaces[0],175)||!close(result.segmentMedianPaces[1],400/3))throw new Error('segment medians');
if(close(result.baselinePace,window.GDataAdapter.median(result.segmentMedianPaces)))throw new Error('old baseline survived');
if(!close(result.indexValues[0],150/175*100)||!close(result.indexValues[1],150/(400/3)*100))throw new Error('index formula');
if(result.segmentStats.some(item=>item.count!==result.count))throw new Error('changing cohort');
if(result.segmentStats.some(item=>item.checkpoint.key==='nolhaga'))throw new Error('Nolhaga required');
"""
        )

    def test_all_race_modes_have_complete_analytical_profiles(self):
        self.run_node(
            r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const data=JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
const expected={'individual-75-2026':9,'individual-35-2026':4,'relay-75-2026':9,'relay-35-2026':4};
for(const [key,count] of Object.entries(expected)){
  const race=adapter.race(key),result=adapter.wholeRacePaceProfile(race.records,race);
  if(result.count<1||result.segmentStats.length!==count||result.indexValues.length!==count)throw new Error(key+' shape');
  if(result.cohort.some(record=>record.status!=='FINISHED'))throw new Error(key+' status');
  if(result.segmentStats.some(stat=>stat.count!==result.count))throw new Error(key+' cohort');
  if(result.segmentStats.some(stat=>stat.checkpoint.key==='nolhaga'))throw new Error(key+' Nolhaga');
  const expectedBaseline=adapter.median(result.cohort.map(record=>record.finish_seconds/race.distanceKm));
  if(Math.abs(result.baselinePace-expectedBaseline)>1e-9)throw new Error(key+' baseline');
}
"""
        )

    def test_main_and_gender_charts_use_whole_race_profiles(self):
        self.assertIn(
            "pacing=adapter.wholeRacePaceProfile(records,race)", self.app
        )
        self.assertIn("values:pacing.indexValues", self.app)
        self.assertIn(
            "retention:adapter.wholeRacePaceProfile(all,race)", self.app
        )
        self.assertIn("values:group.retention.indexValues", self.app)
        self.assertNotIn("baseline=adapter.median(paces)", self.app)

    def test_clubs_get_separate_whole_race_profiles(self):
        self.assertIn(
            "wholeRacePace:wholeRacePaceProfile(members)", self.adapter
        )
        self.assertIn("values:item.wholeRacePace.indexValues", self.interactive)
        self.assertNotIn("base=adapter.median(paces)", self.interactive.split("function renderClubExtras", 1)[1])

    def test_segment_relative_profile_is_unchanged(self):
        self.assertIn(
            "ratio=stat?.medianPace?segment.paceSecondsKm/stat.medianPace:null",
            self.adapter,
        )
        self.assertIn(
            "pacingValues=relative.segments.map(segment=>finite(segment.relative)?100/segment.relative:null)",
            self.app,
        )

    def test_reference_lines_copy_and_cache_versions(self):
        self.assertEqual(self.app.count("referenceValue:100"), 2)
        self.assertIn("referenceValue:100", self.interactive)
        self.assertIn("Fart relativt hela loppet", self.html)
        self.assertIn("100 = medianfart för hela loppet", self.html)
        self.assertIn("100 = respektive köns medianfart över hela loppet", self.html)
        for asset in ("data-adapter.js", "interactive-analysis.js", "app.js"):
            self.assertIn(f"{asset}?v=20260902-whole-race-pace1", self.html)

    def test_source_data_and_nolhaga_are_unchanged(self):
        self.assertEqual(
            sum(len(race["records"]) for race in self.results["races"].values()), 607
        )
        self.assertEqual(len(self.results["splits"]), 4059)
        for race_key, expected in {
            "individual-75-2026": 9,
            "individual-35-2026": 4,
            "relay-75-2026": 9,
            "relay-35-2026": 4,
        }.items():
            checkpoints = self.results["checkpoints"][race_key]
            boundaries = [item for item in checkpoints if item["analysis_boundary"] is not False]
            self.assertEqual(len(boundaries) - 1, expected)
            nolhaga = next(item for item in checkpoints if item["key"] == "nolhaga")
            self.assertFalse(nolhaga["analysis_boundary"])
            self.assertTrue(nolhaga["timing_only"])


if __name__ == "__main__":
    unittest.main()
