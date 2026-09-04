import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
ASSETS=DOCS/'assets'


class CourseDifficultyInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(DOCS/'index.html').read_text(encoding='utf-8')
        cls.app=(ASSETS/'app.js').read_text(encoding='utf-8')
        cls.course=(ASSETS/'course-difficulty.js').read_text(encoding='utf-8')
        cls.map=(ASSETS/'map-engine.js').read_text(encoding='utf-8')
        cls.charts=(ASSETS/'charts.js').read_text(encoding='utf-8')

    def run_node(self,script):
        node=os.environ.get('GOTALEDEN_NODE') or shutil.which('node')
        if not node:self.skipTest('Node.js is required')
        result=subprocess.run([node,'-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr or result.stdout)

    def test_assets_order_section_and_controller_lifecycle(self):
        self.assertIn('id="course-difficulty"',self.html)
        self.assertLess(self.html.index('map-engine.js'),self.html.index('course-difficulty.js'))
        self.assertLess(self.html.index('course-difficulty.js'),self.html.index('app.js'))
        self.assertIn('courseDifficulty:null',self.app)
        self.assertIn('state.courseDifficulty?.destroy();state.courseDifficulty=null',self.app)
        self.assertIn('state.courseDifficulty?.syncFromSegmentLab',self.app)

    def test_route_segment_interpolates_exact_boundaries(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/map-engine.js','utf8'));
const adapter={route:{points:[[0,0,0,0],[10,10,0,10],[20,20,0,20]]},routePoint(distance){return[distance,distance,distance]}};
const points=window.GMapEngine.routeSegment(adapter,2.5,17.5);
if(points[0][0]!==2.5||points.at(-1)[0]!==17.5||points.length!==3)throw new Error(JSON.stringify(points));
""")

    def test_fallback_highlight_create_replace_clear_and_destroy(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/map-engine.js','utf8'));
const highlight={innerHTML:''},runners={innerHTML:''},container={_html:'',set innerHTML(v){this._html=v},get innerHTML(){return this._html},querySelector(s){return s.includes('highlight')?highlight:runners}},adapter={route:{points:[[0,0,0,0],[1,1,0,1],[2,2,0,2]]},routeSlice(){return[[0,0,0],[1,1,1],[2,2,2]]},routePoint(d){return[d,d,d]}};
const map=window.GMapEngine.create(container,{adapter,race:{}});map.highlightRange(.25,.75);const first=highlight.innerHTML;if(!first.includes('route-range-highlight'))throw new Error('create');map.highlightRange(1.25,1.75);if(highlight.innerHTML===first)throw new Error('replace');map.clearHighlight();if(highlight.innerHTML)throw new Error('clear');map.destroy();if(!map.destroyed||container.innerHTML)throw new Error('destroy');
""")

    def test_optional_elevation_highlight_is_backwards_compatible(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));const points=[{route_distance_km:0,elevation_m:0},{route_distance_km:2,elevation_m:10}],checkpoints=[];
if(window.GCharts.elevation(points,checkpoints).includes('elevation-range-highlight'))throw new Error('old call');const html=window.GCharts.elevation(points,checkpoints,{highlightRange:{from:.5,to:1.5}});if(!html.includes('data-highlight-from="0.5"')||!html.includes('data-highlight-to="1.5"'))throw new Error(html);
""")

    def test_selection_is_accessible_synchronized_and_never_scrolls(self):
        for token in ('data-course-row','aria-pressed','onmouseenter','onmouseleave','onfocus','onblur','renderSegmentLab?.()','data-course-distribution'):
            self.assertIn(token,self.course)
        self.assertNotIn('scrollIntoView',self.course)
        self.assertIn('highlightRange?.(',self.course)
        self.assertIn('map?.destroy()',self.course)


if __name__=='__main__':unittest.main()
