import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CourseDifficultyModelTests(unittest.TestCase):
    def run_node(self, script):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_distribution_thresholds_are_central_and_exact(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const summary=window.GDataAdapter.distributionSummary;
const four=summary([1,2,3,4]),five=summary([1,2,3,4,5]),ten=summary(Array.from({length:10},(_,i)=>i+1)),twenty=summary(Array.from({length:20},(_,i)=>i+1));
if(four.available||four.median!==null)throw new Error('n<5');
if(!five.available||!five.smallSample||five.median!==3||five.bandAvailable||five.q25!==null)throw new Error('5-9');
if(!ten.bandAvailable||ten.outerAvailable||ten.q25===null||ten.q10!==null)throw new Error('10-19');
if(!twenty.outerAvailable||twenty.q10===null||twenty.q90===null)throw new Error('20+');
""")

    def test_elevation_range_interpolates_partial_boundaries(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create({races:{},checkpoints:{}},{points:[],full_distance_km:2},{points:[{route_distance_km:0,elevation_m:0},{route_distance_km:1,elevation_m:10},{route_distance_km:2,elevation_m:0}]});
const s=a.elevationRangeStats(.5,1.5);
if(s.startElevationM!==5||s.endElevationM!==5||s.ascentM!==5||s.descentM!==5||s.netElevationM!==0)throw new Error(JSON.stringify(s));
""")

    def test_real_course_profiles_use_stable_complete_cohorts(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),expected={'individual-75-2026':[205,9],'individual-35-2026':[127,4],'relay-75-2026':[94,9],'relay-35-2026':[43,4]};
for(const [key,[count,length]] of Object.entries(expected)){const p=a.courseDifficultyProfile(key);if(p.cohortCount!==count||p.segments.length!==length)throw new Error(key);if(p.segments.some(s=>s.n!==count||!s.pace.bandAvailable||s.name.includes('Nolhaga')))throw new Error('segments '+key);if(p.segments[0].placementMovementMedian!==null||p.segments[0].placementN!==0)throw new Error('start placement');for(const s of p.segments){if(Math.abs(s.paceIndex-p.baselinePace/s.pace.median*100)>.000001||Math.abs(s.slowdownPercent-(s.pace.median/p.baselinePace-1)*100)>.000001)throw new Error('formula')}}
""")

    def test_group_distribution_keeps_one_cohort_for_every_segment(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),race=a.race('individual-75-2026');
for(const sex of ['F','M']){const g=a.segmentGroupDistribution(race,r=>r.sex===sex);if(g.count<10||g.segments.some(s=>s.n!==g.count))throw new Error(sex)}
""")

    def test_source_files_and_counts_remain_unchanged(self):
        data=json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(len(race["records"]) for race in data["races"].values()),607)
        self.assertEqual(len(data["splits"]),4059)


if __name__ == "__main__":
    unittest.main()
