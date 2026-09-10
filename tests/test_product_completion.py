from pathlib import Path
import os
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductCompletionTests(unittest.TestCase):
    def text(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        completed = subprocess.run(
            [node, "-e", body], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_navigation_and_mobile_share_contract(self):
        html = self.text("docs/index.html")
        order = [
            'data-target="runner-lookup"', 'data-target="map-duel"',
            'data-target="overview"', 'data-target="statistics"',
            'data-target="gender"', 'data-target="age-analysis"',
            'data-target="segments"', 'data-target="clubs"',
            'data-target="results"',
        ]
        self.assertEqual(order, sorted(order, key=html.index))
        self.assertIn('aria-label="Dela aktuell vy">Dela</button>', html)
        self.assertIn('id="active-filter-summary"', html)

    def test_phase_a_edge_case_guards(self):
        app = self.text("docs/assets/app.js")
        replay = self.text("docs/assets/runner-replay.js")
        self.assertNotIn("cache:'no-store'", app)
        self.assertIn("requestAnimationFrame", app)
        self.assertIn("setTimeout(filtersChanged,150)", app)
        self.assertIn("aMissing?1:-1", app)
        self.assertIn("finishKey=profile.race.analysisCheckpoints.at(-1)?.key", replay)
        self.assertIn("profile.finish&&last.to?.checkpoint===finishKey", replay)
        self.assertIn("previous.to?.checkpoint!==current.from?.checkpoint", replay)

    def test_personal_summary_contract(self):
        adapter = self.text("docs/assets/data-adapter.js")
        module = self.text("docs/assets/personal-summary.js")
        html = self.text("docs/index.html")
        self.assertIn("function personalRaceSummary(value)", adapter)
        for field in ("fieldPercentile", "classPercentile", "relativeBest",
                      "relativeWeak", "largestPlacementGain",
                      "largestPlacementLoss", "lastAnalysisCheckpoint",
                      "coverage", "referenceLabel", "story"):
            self.assertIn(field, adapter)
        self.assertIn("navigator.share", module)
        self.assertIn("navigator.clipboard", module)
        self.assertIn('aria-live="polite"', module)
        self.assertIn("personal-summary.js?v=20260908-goal-pace1", html)

    def test_faster_than_position_is_strict_tie_safe_and_finished_only(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const records=[
  {bib:'1',name:'A',status:'FINISHED',finish_seconds:100},
  {bib:'2',name:'B',status:'FINISHED',finish_seconds:100},
  {bib:'3',name:'C',status:'FINISHED',finish_seconds:200},
  {bib:'4',name:'D',status:'DNF',finish_seconds:null},
];
const race={section:'Test',type:'individual',gpx_distance_km:1,nominal_distance_km:1,participant:{entity:'person'},records};
const data={races:{r:race},checkpoints:{r:[{key:'start',name:'Start',route_distance_km:0},{key:'finish',name:'Mål',route_distance_km:1}]},splits:[]};
const adapter=window.GDataAdapter.create(data,{full_distance_km:1,points:[[0,0,0,0],[0,0,0,1]]},{points:[]}),items=adapter.race('r').records;
const values=items.map(item=>adapter.percentile(item,items));
if(JSON.stringify(values)!==JSON.stringify([33,33,0,null]))throw new Error(JSON.stringify(values));
""")

    def test_finish_standout_requires_the_actual_finish_segment(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={GCharts:{SEX_COLORS:{F:'#f',M:'#m'},palette:[]}};global.document={};
vm.runInThisContext(fs.readFileSync('docs/assets/interactive-analysis.js','utf8'));
const records=[{id:'missing',status:'FINISHED',isTeam:false},{id:'complete',status:'FINISHED',isTeam:false}];
const race={analysisCheckpoints:[{key:'start'},{key:'middle'},{key:'finish'}]};
const profiles={
  missing:{race,segments:[{to:{checkpoint:'middle'},paceSecondsKm:300,name:'Start–Middle'}]},
  complete:{race,segments:[{to:{checkpoint:'middle'},paceSecondsKm:320,name:'Start–Middle'},{to:{checkpoint:'finish'},paceSecondsKm:280,name:'Middle–Finish'}]},
};
const adapter={statusFinished:item=>item.status==='FINISHED',profile:item=>profiles[item.id],median:values=>values.reduce((sum,value)=>sum+value,0)/values.length,average:values=>values.length?values.reduce((sum,value)=>sum+value,0)/values.length:null,advancements:()=>[],relayClassAdvancements:()=>[],relayClassRecords:()=>records,relativeProfile:()=>({strongest:null})};
const finish=window.GInteractiveAnalysis.standoutData(records,adapter).finish;
if(finish.length!==1||finish[0].record.id!=='complete')throw new Error(JSON.stringify(finish));
""")


if __name__ == "__main__":
    unittest.main()
