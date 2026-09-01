import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class UltravasanParityRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.charts = (DOCS / "assets/charts.js").read_text(encoding="utf-8")
        cls.interactive = (DOCS / "assets/interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.results = json.loads(
            (DOCS / "data/results-2026.json").read_text(encoding="utf-8")
        )

    def test_chart_helpers_cover_fixed_bins_padding_and_fastest_ten_percent(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for chart helper integration tests")
        script = r"""
const fs=require('fs'),vm=require('vm');
global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const c=window.GCharts;
const bins=c.fixedFinishBins([899,900,1799,1800]);
if(bins.step!==900||bins.start!==0)throw new Error('fixed 15-minute boundaries');
if(JSON.stringify(bins.bins.map(bin=>bin.count))!==JSON.stringify([1,2,1]))throw new Error('lost histogram result');
const fastest=c.fastestTenPercentAverage([20,19,18,17,16,15,14,13,12,11,10]);
if(fastest.selectedCount!==2||fastest.totalCount!==11||fastest.value!==10.5)throw new Error('ceil fastest 10 percent');
const single=c.fastestTenPercentAverage([300]);
if(single.selectedCount!==1||single.value!==300)throw new Error('minimum one observation');
const bounds=c.placementPlotBounds(920,320,{l:56,r:20,t:20,b:48});
if(JSON.stringify(bounds.data)!==JSON.stringify({left:64,top:28,right:892,bottom:264}))throw new Error('edge padding');
const scatter=c.scatter([{id:'min',x:1,y:1},{id:'max',x:2,y:2}]);
for(const token of ['data-edge-padding="8"','cx="64" cy="28"','cx="892" cy="264"'])if(!scatter.includes(token))throw new Error('extreme marker '+token);
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_histogram_keeps_shared_gender_colors_and_uses_all_selected_series(self):
        self.assertIn("step=900", self.charts)
        self.assertIn("counts.reduce((sum,values)=>sum+values[index],0)", self.charts)
        self.assertIn("SEX_COLORS=Object.freeze({M:'#2563eb',F:'#db2777'})", self.charts)
        self.assertIn("15-minutersintervall från", self.interactive)
        self.assertIn("fixedFinishBins(finishSeries.flatMap(item=>item.values))", self.interactive)
        app = (DOCS / "assets/app.js").read_text(encoding="utf-8")
        self.assertIn("window.GCharts.fixedFinishBins(times)", app)
        self.assertNotIn("Mitten 50 %", app)

    def test_scatter_zoom_uses_the_same_padded_data_bounds(self):
        for token in (
            "placementPlotBounds(width,height,pad)",
            'data-edge-padding="8"',
            "left:Number(svg.dataset.dataLeft)",
            "top:Number(svg.dataset.dataTop)",
            "right:Number(svg.dataset.dataRight)",
            "bottom:Number(svg.dataset.dataBottom)",
        ):
            self.assertIn(token, self.charts + self.interactive)

    def test_heatmap_defaults_to_median_and_fastest_ten_uses_real_paces(self):
        self.assertIn('data-age-heat-stat="median" aria-pressed="true"', self.html)
        self.assertIn('data-age-heat-stat="fastest10" aria-pressed="false"', self.html)
        self.assertIn("ageHeatStatistic='median'", self.interactive)
        self.assertIn("item.samples.map(segment=>segment.paceSecondsKm)", self.interactive)
        self.assertIn("Math.ceil(valid.length*.1)", self.charts)
        self.assertIn(".sort((a,b)=>a-b)", self.charts)
        self.assertIn("selectedCount} av ${summary.totalCount} giltiga", self.interactive)
        self.assertIn("state.unit==='speed'?`${(3600/value).toFixed(1)} km/h`", self.interactive)

    def test_age_and_relay_group_semantics_remain_distinct(self):
        for label in ("<30", "30–39", "40–49", "50–59", "60+"):
            self.assertIn(f"label:'{label}'", self.interactive)
        self.assertIn("Analytiska åldersgrupper – inte officiella tävlingsklasser", self.interactive)
        self.assertIn("race.isRelay?classGroups", self.interactive)
        self.assertIn("officiella klassnamn", self.interactive)
        self.assertNotIn("relay_leg_assignments", self.html + self.interactive)

    def test_placement_coverage_is_complete_so_no_fallback_is_needed(self):
        missing = lambda value: value is None or value == ""
        expected = {
            "individual-75-2026": 2121,
            "individual-35-2026": 638,
            "relay-75-2026": 1077,
            "relay-35-2026": 223,
        }
        for race_key, count in expected.items():
            passages = [
                split
                for split in self.results["splits"]
                if split["race_key"] == race_key and split["elapsed_seconds"] > 0
            ]
            self.assertEqual(len(passages), count)
            self.assertFalse(any(missing(split.get("place_overall")) for split in passages))
            self.assertFalse(any(missing(split.get("place_class")) for split in passages))
        self.assertNotIn("deriveOverallPlacements", self.interactive)

    def test_product_invariants_and_social_metadata_remain_intact(self):
        self.assertEqual(sum(len(race["records"]) for race in self.results["races"].values()), 607)
        self.assertEqual(len(self.results["splits"]), 4059)
        expected_segments = {
            "individual-75-2026": 9,
            "individual-35-2026": 4,
            "relay-75-2026": 9,
            "relay-35-2026": 4,
        }
        for race_key, count in expected_segments.items():
            checkpoints = self.results["checkpoints"][race_key]
            nolhaga = next(item for item in checkpoints if item["key"] == "nolhaga")
            self.assertFalse(nolhaga["analysis_boundary"])
            self.assertEqual(sum(item["analysis_boundary"] is not False for item in checkpoints) - 1, count)
        for name in (
            "og:title", "og:description", "og:url", "og:type",
            "twitter:card", "twitter:title", "twitter:description",
        ):
            self.assertIn(name, self.html)
        self.assertNotIn("og:image", self.html)
        self.assertNotIn("twitter:image", self.html)
        self.assertIn("instagram.com/stayinhealthyrunning", self.html)
        self.assertIn("youtube.com/playlist", self.html)


if __name__ == "__main__":
    unittest.main()
