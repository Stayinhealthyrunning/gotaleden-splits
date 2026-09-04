import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class AllSegmentAxisLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.charts = (ASSETS / "charts.js").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.interactive = (ASSETS / "interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")
        cls.style = (ASSETS / "style.css").read_text(encoding="utf-8")
        cls.results = json.loads(
            (DOCS / "data/results-2026.json").read_text(encoding="utf-8")
        )

    def test_lines_renders_every_75_and_35_km_axis_label_in_order(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for chart integration tests")
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const axisLabels=labels=>{
  const html=window.GCharts.lines([{name:'Serie',values:labels.map((_,index)=>index+1)}],labels);
  return [...html.matchAll(/<text[^>]+transform="rotate\(-18 [^"]+\)"[^>]*>([^<]+)<\/text>/g)].map(match=>match[1]);
};
const labels75=['Skatås','Kåsjön','Jonsered','Lerum','Floda','Tollered','Norsesund','Västra Bodarna','Mål'];
const labels35=['Tollered','Norsesund','Västra Bodarna','Mål'];
const expected75=['Skatås','Kåsjön','Jonsered','Lerum','Floda','Tollered','Norsesund','Västra Bodarna','Alingsås'];
const expected35=['Tollered','Norsesund','Västra Bodarna','Alingsås'];
if(JSON.stringify(axisLabels(labels75))!==JSON.stringify(expected75))throw new Error('75 km labels');
if(JSON.stringify(axisLabels(labels35))!==JSON.stringify(expected35))throw new Error('35 km labels');
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_line_chart_label_thinning_is_removed(self):
        lines = self.charts.split("function lines(", 1)[1].split("function scatter(", 1)[0]
        self.assertNotIn("Math.ceil(labels.length/8)", lines)
        self.assertNotIn("index%Math.max", lines)
        self.assertIn("labels.forEach((label,index)=>", lines)

    def test_every_relevant_view_uses_the_shared_line_or_flow_chart(self):
        for token in (
            "$('#median-pace').innerHTML=window.GCharts.lines",
            "$('#pacing-chart').innerHTML=window.GCharts.lines",
            "$('#gender-pace').innerHTML=window.GCharts.lines",
            "$('#gender-retention').innerHTML=window.GCharts.lines",
            "$('#age-pace').innerHTML=selected.length?window.GCharts.lines",
            "$('#club-pace').innerHTML=stats.length?window.GCharts.lines",
            "$('#club-pacing-extra').innerHTML=stats.length?window.GCharts.lines",
            "$('#field-flow').innerHTML=window.GCharts.flow",
            "$('#detail-placement').innerHTML=window.GCharts.lines",
            "$('#detail-pacing').innerHTML=window.GCharts.lines",
        ):
            self.assertIn(token, self.app + self.interactive)
        self.assertIn("function flow(items)", self.charts)
        self.assertIn("return lines(series,labels", self.charts)

    def test_existing_full_checkpoint_renderers_remain_complete(self):
        self.assertIn("boundaries.forEach((checkpoint,index,array)=>", self.charts)
        self.assertIn(
            "for(const checkpoint of race.analysisCheckpoints)", self.replay
        )
        self.assertIn(
            "for(const checkpoint of race.analysisCheckpoints)", self.duel
        )
        self.assertIn("${labels.map(label=>`<b>${esc(label)}</b>`).join('')}", self.interactive)

    def test_readability_and_cache_buster_are_preserved(self):
        self.assertIn(".chart{overflow-x:auto;overflow-y:hidden}", self.style)
        self.assertIn(".chart svg{min-width:760px}", self.style)
        self.assertIn(".chart text{font-size:14px}", self.style)
        self.assertIn(".chart:has(>.segment-line-chart),.panel:has(.segment-line-chart){min-width:0}", self.style)
        self.assertIn("'segment-line-chart'", self.charts)
        self.assertIn("rotate(-18", self.charts)
        self.assertIn("assets/charts.js?v=20260904-journey1", self.html)
        self.assertIn("assets/style.css?v=20260904-journey1", self.html)

    def test_data_and_nolhaga_invariants_are_unchanged(self):
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
            self.assertTrue(nolhaga["timing_only"])
            self.assertFalse(nolhaga["analysis_boundary"])
            self.assertNotIn("Nolhaga", [item["name"] for item in boundaries])


if __name__ == "__main__":
    unittest.main()
