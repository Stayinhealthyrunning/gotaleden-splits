import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChartAxisPaddingTests(unittest.TestCase):
    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        completed = subprocess.run([node, "-e", body], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_formatted_line_labels_expand_the_plot_margin(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));const c=window.GCharts,left=html=>Number(html.match(/class="gridline" x1="([\d.]+)/)[1]),labelX=html=>Number(html.match(/<text x="([\d.]+)"[^>]*text-anchor="end"/)[1]);
const short=c.lines([{name:'x',values:[100,101]}],['A','B'],{format:()=> '100'}),pace=c.lines([{name:'x',values:[100,101]}],['A','B'],{format:()=> '7:09 /km'}),speed=c.lines([{name:'x',values:[100,101]}],['A','B'],{format:()=> '12,4 km/h'});
if(left(pace)<=left(short)||left(pace)<=58||left(speed)<left(pace))throw new Error('long labels did not expand margin');if(labelX(pace)<0||!pace.includes('7:09 /km')||!speed.includes('12,4 km/h'))throw new Error('formatted label clipped');if(left(short)>70)throw new Error('short label margin too large');
""")

    def test_other_numeric_y_axes_use_dynamic_padding(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));const c=window.GCharts,left=html=>Number(html.match(/class="gridline" x1="([\d.]+)/)[1]);
const scatterShort=c.scatter([{x:1,y:1},{x:2,y:2}],{yFormat:()=> '100'}),scatterLong=c.scatter([{x:1,y:1},{x:2,y:2}],{yFormat:()=> '12,4 km/h'});if(left(scatterLong)<=left(scatterShort))throw new Error('scatter padding');
const histogram=c.histogramSeries([{name:'x',values:Array(12345).fill(3600)}]);if(left(histogram)<=44)throw new Error('histogram padding');
const elevationShort=c.elevation([{route_distance_km:0,elevation_m:0},{route_distance_km:1,elevation_m:100}],[]),elevationLong=c.elevation([{route_distance_km:0,elevation_m:12000},{route_distance_km:1,elevation_m:12340}],[]);if(left(elevationLong)<=left(elevationShort))throw new Error('elevation padding');
""")


if __name__ == "__main__":
    unittest.main()
