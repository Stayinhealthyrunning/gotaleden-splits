import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class GenderChartsDuelRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.css = (ASSETS / "style.css").read_text(encoding="utf-8")
        cls.charts = (ASSETS / "charts.js").read_text(encoding="utf-8")
        cls.interactive = (ASSETS / "interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")

    def test_only_requested_feature_grids_are_equal_on_desktop(self):
        self.assertEqual(self.html.count('class="feature-grid equal-panels"'), 2)
        self.assertIn(
            ".feature-grid.equal-panels{grid-template-columns:repeat(2,minmax(0,1fr))}",
            self.css,
        )
        self.assertIn(
            ".feature-grid,.feature-grid.equal-panels{grid-template-columns:1fr}",
            self.css,
        )

    def test_analysis_points_have_no_white_stroke(self):
        self.assertIn(".point{stroke:none}", self.css)
        self.assertIn(".scatter-point{cursor:pointer;stroke:none", self.css)
        self.assertIn(".runner-marker", self.css)
        self.assertIn("stroke:#fff", self.css)

    def test_gender_offsets_and_reference_line_execute(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for chart integration tests")
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const lines=window.GCharts.lines([
  {id:'F',name:'Kvinnor',color:'#db2777',values:[100,101]},
  {id:'M',name:'Män',color:'#2563eb',values:[100,101]}
],['A','B'],{referenceValue:100});
for(const token of ['data-series="F" data-visual-offset-x="-2.5"','data-series="M" data-visual-offset-x="2.5"','class="reference-line" data-reference-value="100"','class="reference-label"'])if(!lines.includes(token))throw new Error(token);
if((lines.match(/>100<\/text>/g)||[]).length!==1)throw new Error('duplicate 100 labels');
const scatter=window.GCharts.scatter([{id:'f',sex:'F',x:10,y:2},{id:'m',sex:'M',x:10,y:2}]);
for(const token of ['data-sex="F" data-visual-offset-x="-2.5"','data-sex="M" data-visual-offset-x="2.5"'])if(!scatter.includes(token))throw new Error(token);
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_gender_series_and_both_reference_100_calls_are_wired(self):
        self.assertIn("({id:sex,name:sexMeta[sex].label", self.interactive)
        self.assertIn("({id:group.sex,name:group.label", self.app)
        self.assertEqual(self.app.count("referenceValue:100"), 2)
        self.assertIn(".reference-line", self.css)
        self.assertIn("stroke-dasharray:6 5", self.css)

    def test_dnf_and_segment_character_are_split_by_gender(self):
        self.assertIn("data-dnf-sex", self.interactive)
        self.assertIn(
            "adapter.dnfByLastAnalysisCheckpoint(records.filter(record=>record.sex===sex))",
            self.interactive,
        )
        self.assertIn("data-segment-sex", self.interactive)
        self.assertIn(
            "adapter.segmentStats(records.filter(record=>record.sex===sex))",
            self.interactive,
        )
        self.assertIn("item?.count||0", self.interactive)

    def test_percentiles_use_finished_results_per_gender(self):
        self.assertIn("data-percentile-sex", self.interactive)
        self.assertIn(
            "record.sex===sex&&adapter.statusFinished(record)", self.interactive
        )
        self.assertIn("window.GCharts.percentileLadder(finishTimes", self.interactive)

    def test_duel_duration_and_finish_audio_contract(self):
        self.assertIn("const BASE_PLAYBACK_SECONDS=180", self.duel)
        self.assertIn("maxTime/BASE_PLAYBACK_SECONDS", self.duel)
        self.assertIn("audio.loop=false", self.duel)
        self.assertIn("function finishAnimation(){stop()}", self.duel)
        self.assertIn("if(time>=maxTime)finishAnimation()", self.duel)
        self.assertIn("function stop({pauseAudio=true}={})", self.duel)
        self.assertIn("if(pauseAudio)audio?.pause()", self.duel)
        self.assertIn("if(playing){stop();return}", self.duel)
        self.assertIn("playAudio();lastFrame=performance.now()", self.duel)
        self.assertIn("if(time>=maxTime){time=0;if(audio)audio.currentTime=0}", self.duel)
        self.assertIn("function reset(){stop();time=0", self.duel)
        self.assertIn("if(audio)audio.currentTime=0", self.duel)
        self.assertIn("audio.loop=true", self.replay)


if __name__ == "__main__":
    unittest.main()
