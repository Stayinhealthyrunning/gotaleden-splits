import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


class DistributionBandChartTests(unittest.TestCase):
    def run_node(self,script):
        node=os.environ.get('GOTALEDEN_NODE') or shutil.which('node')
        if not node:self.skipTest('Node.js is required')
        result=subprocess.run([node,'-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr or result.stdout)

    def test_band_median_outer_tooltip_and_interactive_click_targets(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const d=(n,median,q25=null,q75=null,q10=null,q90=null)=>({n,median,q25,q75,q10,q90,bandAvailable:n>=10,outerAvailable:n>=20,smallSample:n>=5&&n<10});
const html=window.GCharts.distributionBand([{id:'F',name:'Kvinnor',color:'#db2777',n:20,segments:[d(20,360,330,390,310,420),d(7,370)]}],['A','B'],{format:v=>Math.round(v)+'s',unitLabel:' /km',interactiveSegments:true});
for(const token of ['class="distribution-band"','class="plot-line distribution-median"','data-series="F"','data-course-segment="0"','tabindex="0"','role="button"','Q25–Q75: 330s–390s /km','Q10–Q90: 310s–420s /km','n=7 · Litet underlag'])if(!html.includes(token))throw new Error(token);
if((html.match(/class="distribution-band"/g)||[]).length!==1)throw new Error('small sample band');
""")

    def test_default_is_noninteractive_and_legend_explains_small_samples(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const full={n:20,median:360,q25:330,q75:390,q10:310,q90:420,bandAvailable:true,outerAvailable:true},html=window.GCharts.distributionBand([{id:'F',name:'Kvinnor',n:20,segments:[full]},{id:'small',name:'Tre',n:3,segments:[{n:3,median:null,bandAvailable:false}]},{id:'median',name:'Sju',n:7,segments:[{n:7,median:370,bandAvailable:false,smallSample:true}]}],['A']);
for(const token of ['class="distribution-band"','class="plot-line distribution-median"','<title>','Tre · n=3 · För litet underlag','Sju · n=7 · Litet underlag'])if(!html.includes(token))throw new Error(token);
for(const token of ['data-course-segment','role="button"','tabindex="0"'])if(html.includes(token))throw new Error('false interaction '+token);
""")

    def test_missing_values_break_median_and_band_paths(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const ok={n:10,median:5,q25:4,q75:6,bandAvailable:true},missing={n:0,median:null,q25:null,q75:null,bandAvailable:false};
const html=window.GCharts.distributionBand([{name:'Fält',segments:[ok,missing,ok]}],['A','B','C']);
if((html.match(/class="distribution-band"/g)||[]).length!==2)throw new Error('band runs');
const path=html.match(/distribution-median[^>]+d="([^"]+)/)[1];if((path.match(/M/g)||[]).length!==2)throw new Error(path);
""")

    def test_dynamic_left_padding_uses_formatted_ticks(self):
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const html=window.GCharts.distributionBand([{name:'A',segments:[{n:10,median:100,q25:90,q75:110,bandAvailable:true}]}],['A'],{format:()=> 'mycket långt värde'}),left=Number(html.match(/class="gridline" x1="([\d.]+)/)[1]);if(left<=58)throw new Error(left);
""")


if __name__=='__main__':unittest.main()
