import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class HeadToHeadAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.runtime = (ASSETS / "head-to-head.js").read_text(encoding="utf-8")
        cls.adapter = (ASSETS / "data-adapter.js").read_text(encoding="utf-8")
        cls.style = (ASSETS / "style.css").read_text(encoding="utf-8")

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        result = subprocess.run([node, "-e", body], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout.strip()

    def test_complete_modes_use_expected_segments_and_one_stable_reference(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),out={};
for(const key of ['individual-75-2026','individual-35-2026','relay-75-2026','relay-35-2026']){const race=a.race(key),pair=a.journeyCompleteProfiles(race).slice(0,2).map(x=>x.record),h=a.headToHeadAnalysis(race,pair[0],pair[1]);out[key]=[h.sharedCheckpoints.length,h.segments.length,h.coverage.comparableSegments,h.fieldReference.count,h.insights.finalGapSeconds!==null,h.segments.every(s=>s.referenceMedianPace===h.fieldReference.checkpoints[s.index].medianPace)]}
console.log(JSON.stringify(out));
""")
        self.assertEqual(json.loads(output), {
            "individual-75-2026": [9, 9, 9, 205, True, True],
            "individual-35-2026": [4, 4, 4, 127, True, True],
            "relay-75-2026": [9, 9, 9, 94, True, True],
            "relay-35-2026": [4, 4, 4, 43, True, True],
        })

    def test_exact_gap_segment_delta_equal_missing_and_rejections(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const source=JSON.parse(fs.readFileSync('docs/data/results-2026.json'));
function run(aTime,bTime,missing=false){const d=structuredClone(source),key='individual-75-2026',a='785',b='777';for(const split of d.splits){if(split.race_key===key&&split.checkpoint==='skatas'&&split.bib===a)split.elapsed_seconds=aTime;if(split.race_key===key&&split.checkpoint==='skatas'&&split.bib===b)split.elapsed_seconds=bTime}if(missing)d.splits=d.splits.filter(s=>!(s.race_key===key&&s.bib===b&&s.checkpoint==='skatas'));const x=window.GDataAdapter.create(d,JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),h=x.headToHeadAnalysis(key,key+':'+a,key+':'+b);return[h.checkpoints[0].gapSeconds,h.segments[0].segmentDeltaSeconds,h.segments[0].winner,h.sharedCheckpoints.some(p=>p.checkpoint==='skatas')]}
const base=window.GDataAdapter.create(source,JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
console.log(JSON.stringify({ahead:run(1000,1060),behind:run(1120,1060),equal:run(1060,1060),missing:run(1000,1060,true),same:base.headToHeadAnalysis('individual-75-2026','individual-75-2026:785','individual-75-2026:785'),different:base.headToHeadAnalysis('individual-75-2026','individual-75-2026:785','individual-35-2026:1540')}));
""")
        out = json.loads(output)
        self.assertEqual(out["ahead"], [60, 60, "a", True])
        self.assertEqual(out["behind"], [-60, -60, "b", True])
        self.assertEqual(out["equal"], [0, 0, "equal", True])
        self.assertEqual(out["missing"], [None, None, None, False])
        self.assertIsNone(out["same"])
        self.assertIsNone(out["different"])

    def test_observed_lead_changes_and_most_time_won(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));const source=JSON.parse(fs.readFileSync('docs/data/results-2026.json')),key='individual-75-2026',ids=['785','777'],cps=['skatas','kasjon','jonsered','lerum','floda','tollered','norsesund','vastra_bodarna','alingsas'];function analyze(gaps){const d=structuredClone(source),a=cps.map((_,i)=>(i+1)*1000),b=a.map((v,i)=>v+gaps[i]);for(const s of d.splits){const i=cps.indexOf(s.checkpoint),side=ids.indexOf(s.bib);if(s.race_key===key&&i>=0&&side>=0)s.elapsed_seconds=(side===0?a:b)[i]}for(const r of d.races[key].records){if(r.bib===ids[0])r.finish_seconds=a.at(-1);if(r.bib===ids[1])r.finish_seconds=b.at(-1)}const x=window.GDataAdapter.create(d,JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));return x.headToHeadAnalysis(key,key+':785',key+':777')}const h=analyze([60,30,-10,-20,5,5,5,5,5]),most=analyze([60,30,150,-50,-50,-50,-50,-50,-50]);console.log(JSON.stringify({gaps:h.sharedCheckpoints.slice(0,5).map(x=>x.gapSeconds),flips:h.insights.leadChanges,a:most.insights.mostTimeWonA.segmentDeltaSeconds,b:most.insights.mostTimeWonB.segmentDeltaSeconds}));
""")
        out = json.loads(output)
        self.assertEqual(out["gaps"], [60, 30, -10, -20, 5])
        self.assertEqual(out["flips"], 2)
        self.assertEqual(out["a"], 120)
        self.assertEqual(out["b"], -200)

    def test_real_dnf_has_no_fabricated_finish_or_later_winner(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),race=a.race('individual-75-2026'),dnf=race.records.find(r=>r.status==='DNF'&&a.profile(r).analysisAnchors.length>1),fin=a.journeyCompleteProfiles(race)[0].record,h=a.headToHeadAnalysis(race,fin,dnf),finish=h.checkpoints.at(-1);console.log(JSON.stringify({status:h.b.summary.status,final:h.insights.finalGapSeconds,finish:finish.elapsedB,winner:h.segments.at(-1).winner,shared:h.sharedCheckpoints.length,coverage:h.b.summary.checkpointCount}));
""")
        out = json.loads(output)
        self.assertEqual(out["status"], "DNF")
        self.assertIsNone(out["final"])
        self.assertIsNone(out["finish"])
        self.assertIsNone(out["winner"])
        self.assertEqual(out["shared"], out["coverage"])

    def test_launcher_and_canonical_url_roundtrip(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));vm.runInThisContext(fs.readFileSync('docs/assets/head-to-head.js','utf8'));const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),records=['individual-75-2026:785','individual-75-2026:777'].map(id=>a.record(id)),url=window.GHeadToHead.shareUrl('https://example.test/?old=1#x','individual-75-2026',records),resolved=window.GHeadToHead.resolveUrl(new URL(url).search,a);console.log(JSON.stringify({states:[0,1,2,3,5].map(n=>window.GHeadToHead.launcherState(n,false)),url,ids:resolved.records.map(r=>r.id),bad:window.GHeadToHead.resolveUrl('?race=individual-75-2026&compare=bad,bad',a)}));
""")
        out = json.loads(output)
        self.assertEqual([s["enabled"] for s in out["states"]], [False, False, True, False, False])
        self.assertEqual([s["label"] for s in out["states"]], ["Välj två deltagare", "Välj en deltagare till", "Jämför två lopp", "Jämförelse kräver exakt två", "Jämförelse kräver exakt två"])
        self.assertIn("race=individual-75-2026", out["url"])
        self.assertEqual(out["ids"], ["individual-75-2026:785", "individual-75-2026:777"])
        self.assertIsNone(out["bad"])

    def test_runtime_wiring_is_scoped_and_reuses_map_and_duel(self):
        for token in ('id="open-head-to-head"', 'assets/head-to-head.js?v=20260907-head-to-head1'):
            self.assertIn(token, self.index)
        self.assertLess(self.index.index("map-duel.js"), self.index.index("head-to-head.js"))
        for token in ("GHeadToHead.open", "GHeadToHead.resolveUrl", "onKartduell", "state.duelIds=pair.map", "openDuelDialog()"):
            self.assertIn(token, self.app)
        for token in ("'head-to-head-dialog'", "map?.destroy()", "GMapEngine.create", "highlightRange", "GCharts.elevation", "aria-pressed", "removeCompare", "history.replaceState"):
            self.assertIn(token, self.runtime)
        self.assertIn(".head-to-head-dialog", self.style)
        self.assertIn("@media(max-width:620px)", self.style)
        self.assertNotIn("GRunnerReplay", self.runtime)
        self.assertNotIn("audio", self.runtime.lower())

    def test_no_nolhaga_analysis_point_and_relay_is_team_based(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json'))),race=a.race('relay-75-2026'),pair=a.journeyCompleteProfiles(race).slice(0,2).map(x=>x.record),h=a.headToHeadAnalysis(race,...pair),free=race.records.find(r=>!a.relayClassMeta(r).ranked),hf=a.headToHeadAnalysis(race,pair[0],free);console.log(JSON.stringify({nolhaga:h.checkpoints.some(x=>x.checkpoint==='nolhaga')||h.segments.some(x=>x.from==='nolhaga'||x.to==='nolhaga'),type:h.a.record.displayType,relay:h.a.summary.relayClass.id,free:hf.b.summary.relayClass.ranked,classPlace:hf.b.summary.classPlace,sex:h.a.summary.sex}));
""")
        out = json.loads(output)
        self.assertFalse(out["nolhaga"])
        self.assertEqual(out["type"], "lag")
        self.assertFalse(out["free"])
        self.assertIsNone(out["classPlace"])
        self.assertNotIn("sex", out)


if __name__ == "__main__":
    unittest.main()
