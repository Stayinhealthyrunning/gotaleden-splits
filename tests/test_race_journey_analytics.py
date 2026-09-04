import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class RaceJourneyAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.adapter = (ASSETS / "data-adapter.js").read_text(encoding="utf-8")
        cls.charts = (ASSETS / "charts.js").read_text(encoding="utf-8")
        cls.journey = (ASSETS / "profile-journey.js").read_text(encoding="utf-8")
        cls.css = (ASSETS / "style.css").read_text(encoding="utf-8")
        cls.results = json.loads((DOCS / "data/results-2026.json").read_text(encoding="utf-8"))

    def run_node(self, script):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for journey integration tests")
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_journey_assets_are_ordered_and_lifecycle_is_scoped_to_detail(self):
        for asset in ("data-adapter.js", "runner-replay.js", "app.js"):
            self.assertIn(f"{asset}?v=20260904-journey1", self.html)
        for asset in ("charts.js", "profile-journey.js", "style.css"):
            self.assertIn(f"{asset}?v=20260904-journey2", self.html)
        self.assertLess(self.html.index("runner-replay.js"), self.html.index("profile-journey.js"))
        self.assertLess(self.html.index("profile-journey.js"), self.html.index("app.js"))
        self.assertIn("journey:null", self.app)
        self.assertIn("state.journey?.destroy();state.journey=null", self.app)
        self.assertIn("window.GProfileJourney.create($('#profile-journey'),{adapter,record,replay:state.replay})", self.app)

    def test_complete_finished_cohorts_are_constant_and_require_9_or_4_real_segments(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const adapter=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
const expected={'individual-75-2026':[205,9],'individual-35-2026':[127,4],'relay-75-2026':[94,9],'relay-35-2026':[43,4]};
for(const [key,[count,segments]] of Object.entries(expected)){
  const race=adapter.race(key),cohort=adapter.journeyCompleteProfiles(race);
  if(cohort.length!==count)throw new Error('count '+key+' '+cohort.length);
  if(cohort.some(profile=>profile.record.status!=='FINISHED'||profile.segments.length!==segments))throw new Error('cohort '+key);
  const record=cohort[0].record,refs=adapter.journeyReferences(record);
  for(const ref of refs.references)if(ref.available&&(ref.checkpoints.length!==segments||ref.checkpoints.some(point=>point.medianElapsed===null||point.medianPace===null)))throw new Error('stable '+key+' '+ref.id);
  if(refs.references.some(ref=>ref.checkpoints.some(point=>point.key==='nolhaga')))throw new Error('nolhaga '+key);
}
""")

    def test_gap_and_pacing_formulas_have_the_requested_direction(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create({races:{},checkpoints:{}},{points:[],full_distance_km:0},{profile:[]});
if(a.journeyGap(3600,3540)!==60||a.journeyGap(3600,3660)!==-60)throw new Error('gap sign');
if(Math.abs(a.journeyRelativePerformance(360,330)-9.090909)>0.0001)throw new Error('pace formula');
if(a.journeyPacingCategory(9).id!=='very-strong'||a.journeyPacingCategory(-9).id!=='very-weak'||a.journeyPacingCategory(0).id!=='level')throw new Error('categories');
""")
        self.assertIn("före", self.journey)
        self.assertIn("efter", self.journey)

    def test_gap_words_use_unsigned_duration_after_reference(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/profile-journey.js','utf8'));
const gap=window.GProfileJourney.gapWords,label='Hela fältet';
if(gap(60,label)!=='+1:00 före Hela fältet')throw new Error('positive '+gap(60,label));
if(gap(-60,label)!=='1:00 efter Hela fältet')throw new Error('negative '+gap(-60,label));
if(gap(0,label)!=='0:00, i nivå med Hela fältet')throw new Error('zero '+gap(0,label));
if(gap(-3661,label)!=='1:01:01 efter Hela fältet')throw new Error('hours '+gap(-3661,label));
""")

    def test_real_observations_dnf_and_mixed_free_are_never_fabricated(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
const dnf=a.race('individual-75-2026').records.find(record=>record.status==='DNF'),journey=a.journeyAnalysis(dnf);
if(journey.gapPoints.at(-1).gapSeconds!==null||journey.placementPoints.at(-1).overall!==null||journey.pacing.at(-1).ownPace!==null)throw new Error('false DNF finish');
if(journey.gapPoints.some(point=>point.sourceType&&point.sourceType!=='official'))throw new Error('gap source');
const mixed=a.race('relay-75-2026').records.find(record=>!a.relayClassMeta(record).ranked),mixedJourney=a.journeyAnalysis(mixed);
if(mixedJourney.references.some(reference=>reference.id==='sex'))throw new Error('relay sex');
if(mixedJourney.placementSeries.class.available||mixedJourney.placementSeries.class.values.some(value=>value!==null)||!mixedJourney.placementSeries.class.message.includes('Ej tävling'))throw new Error('mixed class');
if(!mixedJourney.references.find(reference=>reference.id==='class').available)throw new Error('mixed analytical reference');
""")
        self.assertNotIn("stateAtTime", self.journey)

    def test_reference_sample_threshold_and_small_warning_use_real_cohorts(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const a=window.GDataAdapter.create(JSON.parse(fs.readFileSync('docs/data/results-2026.json')),JSON.parse(fs.readFileSync('docs/data/route.json')),JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json')));
const r75=a.race('relay-75-2026'),small=r75.records.find(record=>a.journeyReferences(record).class.count<5),smallRef=a.journeyReferences(small).class;
if(smallRef.available||smallRef.message!=='För litet underlag')throw new Error('under five');
const r35=a.race('relay-35-2026'),five=r35.records.find(record=>{const ref=a.journeyReferences(record).class;return ref.count>=5&&ref.count<10}),fiveRef=a.journeyReferences(five).class;
if(!fiveRef.available||!fiveRef.smallSample||fiveRef.message!=='Litet underlag')throw new Error('five to nine');
const normal=a.journeyReferences(a.race('individual-75-2026').records[0]).field;if(!normal.available||normal.smallSample)throw new Error('ten plus');
""")
        self.assertIn("const MIN_REFERENCE_SIZE=5", self.adapter)

    def test_chart_helpers_break_missing_paths_and_invert_rank_axis(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const signed=window.GCharts.signedJourney([{label:'A',value:60,distance:1,title:'a'},{label:'B',value:null,distance:2,title:'b'},{label:'C',value:-60,distance:3,title:'c'}]);
if(!signed.includes('journey-zero')||(signed.match(/M/g)||[]).length<2||!signed.includes('data-journey-distance="1"'))throw new Error('signed missing break');
if(!signed.includes('>0:00</text>')||signed.includes('0:00 = jämförelsegruppen'))throw new Error('zero reference label');
const rank=window.GCharts.rankJourney([{id:'overall',name:'Total',color:'#000',values:[20,null,1],distances:[1,2,3]}],['A','B','C']);
const circles=[...rank.matchAll(/cy="([0-9.]+)" r="5"/g)].map(match=>Number(match[1]));if(circles.length!==2||!(circles[1]<circles[0]))throw new Error('rank direction');
if((rank.match(/data-journey-distance=/g)||[]).length!==2)throw new Error('missing rank point');
""")

    def test_journey_seek_is_keyboard_accessible_and_never_autoplays(self):
        self.assertIn("replay.seekDistance(distance)", self.journey)
        self.assertIn("event.key==='Enter'||event.key===' '", self.journey)
        self.assertIn("if(element.tagName!=='BUTTON')element.onkeydown", self.journey)
        self.assertIn("midpointDistance", self.adapter)
        for forbidden in ("replay.toggle(", "audio.play(", "replay.play("):
            self.assertNotIn(forbidden, self.journey)

    def test_journey_precedes_insights_in_flex_and_desktop_grid(self):
        flex = (
            "#detail-replay{order:4}#profile-journey{order:5;min-width:0}.insight-cards{order:6}"
            ".detail-grid{order:7}.split-section{order:8}"
        )
        desktop = (
            "#detail-replay{grid-column:1/-1;grid-row:3}#profile-journey{grid-column:1/-1;grid-row:4}"
            ".insight-cards{grid-column:1/-1;grid-row:5}.detail-grid{grid-column:1/-1;grid-row:6}"
            ".split-section{grid-column:1/-1;grid-row:7}"
        )
        self.assertIn(flex, self.css)
        self.assertIn(desktop, self.css)

    def test_gap_chart_explains_the_dynamic_zero_reference_in_copy(self):
        self.assertIn("0:00 motsvarar ${esc(reference.label)}", self.journey)
        self.assertNotIn("0:00 = jämförelsegruppen", self.charts)

    def test_individual_scatter_is_half_transparent_without_changing_relay(self):
        self.assertIn("fill-opacity=\"${individualSex?'.5':'1'}\"", self.charts)
        self.assertIn("point.sex==='F'||point.sex==='M'", self.charts)
        self.assertIn('.scatter-point[data-sex="M"],.scatter-point[data-sex="F"]{fill-opacity:.5}', self.css)
        self.assertIn('data-result-id="${esc(point.id)}"', self.charts)

    def test_responsive_layout_and_trust_copy_are_present(self):
        for token in (
            ".journey-grid{display:grid;grid-template-columns:repeat(2",
            "@media(max-width:620px)",
            ".journey-ribbon{display:grid;grid-auto-columns:158px",
            "LOPPETS UTVECKLING",
            "Så räknas det",
            "Nolhaga är timing-/replayankare men inte analysgräns",
        ):
            self.assertIn(token, self.css if token.startswith(".") or token.startswith("@") else self.journey)

    def test_source_counts_and_nolhaga_metadata_are_unchanged(self):
        self.assertEqual(sum(len(race["records"]) for race in self.results["races"].values()), 607)
        self.assertEqual(len(self.results["splits"]), 4059)
        for key, expected in (("individual-75-2026", 9), ("relay-75-2026", 9), ("individual-35-2026", 4), ("relay-35-2026", 4)):
            checkpoints = self.results["checkpoints"][key]
            self.assertEqual(sum(checkpoint.get("analysis_boundary") is not False for checkpoint in checkpoints) - 1, expected)
            nolhaga = next((checkpoint for checkpoint in checkpoints if checkpoint["key"] == "nolhaga"), None)
            if nolhaga:
                self.assertTrue(nolhaga["timing_only"])
                self.assertTrue(nolhaga["speaker_checkpoint"])
                self.assertTrue(nolhaga["replay_anchor"])
                self.assertFalse(nolhaga["analysis_boundary"])


if __name__ == "__main__":
    unittest.main()
