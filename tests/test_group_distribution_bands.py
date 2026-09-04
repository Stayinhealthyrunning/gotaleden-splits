import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs'/'assets'


class GroupDistributionBandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=(ASSETS/'app.js').read_text(encoding='utf-8')
        cls.interactive=(ASSETS/'interactive-analysis.js').read_text(encoding='utf-8')
        cls.charts=(ASSETS/'charts.js').read_text(encoding='utf-8')

    def run_node(self,script):
        node=os.environ.get('GOTALEDEN_NODE') or shutil.which('node')
        if not node:self.skipTest('Node.js is required')
        result=subprocess.run([node,'-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr or result.stdout)

    def test_individual_and_relay_counts_apply_thresholds(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
const i75=a.race('individual-75-2026'),sex=Object.fromEntries(['F','M'].map(id=>[id,a.segmentGroupDistribution(i75,r=>r.sex===id)]));if(sex.F.count!==42||sex.M.count!==163||[...sex.F.segments,...sex.M.segments].some(s=>!s.pace.bandAvailable))throw new Error('sex');
const expected={'relay-75-2026':{men:16,women:3,'mixed-ranked':13,'mixed-free':62},'relay-35-2026':{men:2,women:5,'mixed-ranked':15,'mixed-free':21}};for(const [key,counts] of Object.entries(expected)){const race=a.race(key);for(const group of a.relayClassGroups(race.records,race)){const d=a.segmentGroupDistribution(race,r=>a.relayClassMeta(r).id===group.id),n=counts[group.id];if(d.count!==n||d.segments.some(s=>s.pace.bandAvailable!==(n>=10)||s.pace.available!==(n>=5)))throw new Error(key+' '+group.id)}}
""")

    def test_relay_colors_and_noncompetitive_label_are_retained(self):
        self.assertIn("color:group.color",self.app)
        self.assertIn("color:group.color",self.interactive)
        self.assertIn("group.ranked?'':' · Ej tävling'",self.app)
        self.assertIn("group.ranked?'':' · Ej tävling'",self.interactive)
        self.assertNotIn('record.sex===sex',self.interactive.split('function renderRelayExploration',1)[1].split('function renderSexExploration',1)[0])

    def test_speed_quantiles_are_recomputed_from_observations(self):
        for source in (self.app,self.interactive):
            self.assertIn('adapter.distributionSummary(segment.samples.map(sample=>3600/sample.paceSecondsKm))',source)

    def test_toggles_remove_the_whole_series_and_band_elements_share_id(self):
        self.assertIn("filter(sex=>sexViews.pace[sex])",self.interactive)
        self.assertIn("filter(group=>relayViews.pace.has(group.id))",self.interactive)
        self.assertIn('class="distribution-band" data-series=',self.charts)
        self.assertIn('distribution-median" data-series=',self.charts)


if __name__=='__main__':unittest.main()
