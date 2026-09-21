import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class AcceptanceFixesOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.charts = (ASSETS / "charts.js").read_text(encoding="utf-8")
        cls.course = (ASSETS / "course-difficulty.js").read_text(encoding="utf-8")
        cls.map_engine = (ASSETS / "map-engine.js").read_text(encoding="utf-8")
        cls.playback = (ASSETS / "playback.js").read_text(encoding="utf-8")
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")

    def run_node(self, script):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_duplicate_panels_are_not_in_static_page(self):
        self.assertNotIn('id="median-pace"', self.html)
        self.assertNotIn('id="pacing-chart"', self.html)
        self.assertNotIn("LOPPETS DYNAMIK", self.html)
        self.assertNotIn("Fart relativt hela loppet", self.html)
        self.assertNotIn('id="detail-placement"', self.app)
        self.assertNotIn("$('#detail-placement')", self.app)
        self.assertIn('<section class="detail-grid single">', self.app)

    def test_all_women_and_men_use_group_correct_methods(self):
        for token in ("{id:'all',name:'Alla'", "{id:'F',name:'Kvinnor'", "{id:'M',name:'Män'"):
            self.assertIn(token, self.app)
        self.assertIn("adapter.segmentGroupDistribution(race,definition.test,records)", self.app)
        self.assertIn("adapter.wholeRacePaceProfile(records.filter(definition.test),race)", self.app)

    def test_percentile_positions_use_actual_times_on_one_domain(self):
        self.assertNotIn("--step:${index}", self.charts)
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/charts.js','utf8'));
const q=(values,p)=>{const s=values.slice().sort((a,b)=>a-b),i=(s.length-1)*p,l=Math.floor(i),h=Math.ceil(i);return s[l]+(s[h]-s[l])*(i-l)};
const html=window.GCharts.percentileTimeline([
 {name:'A',color:'#111',values:[1000,2000,3000,4000,5000]},
 {name:'B',color:'#222',values:[2000,4000,6000,8000,10000]}
],q);
if(!html.includes('data-time-min=')||!html.includes('data-time-max='))throw new Error('domain');
if((html.match(/class="percentile-marker"/g)||[]).length!==10)throw new Error('markers');
const points=[...html.matchAll(/data-percentile-time="([\d.]+)" cx="([\d.]+)"/g)].map(m=>({t:+m[1],x:+m[2]}));
for(let i=1;i<5;i++)if(points[i].t>points[i+5].t&&points[i].x<=points[i+5].x)throw new Error('time geometry');
if(!(points[0].x<points[5].x))throw new Error('shared scale');
"""
        self.run_node(script)

    def test_map_highlight_has_dedicated_front_pane_and_replaces(self):
        for token in (
            "map.createPane(highlightPaneName)",
            "highlightPane.style.zIndex='475'",
            "pane:highlightPaneName",
            "function highlightRange(fromDistance,toDistance,options={}){clearHighlight()",
            "data-map-highlight-from",
            "data-map-highlight-to",
        ):
            self.assertIn(token, self.map_engine)
        self.assertIn("map.highlightRange?.(segment.fromDistance,segment.toDistance)", self.course)
        self.assertIn("restore=()=>applyHighlight(selectedSegmentIndex", self.course)

    def test_shared_90_second_playback_and_audio_fade_lifecycle(self):
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/playback.js','utf8'));
const p=window.GRacePlayback;
if(p.BASE_PLAYBACK_SECONDS!==90||p.AUDIO_FADE_SECONDS!==5)throw new Error('constants');
if(p.raceDelta(36000,90000,1)!==36000)throw new Error('1x duration');
if(p.raceDelta(36000,45000,2)!==36000)throw new Error('2x duration');
let queue=[],cancelled=new Set(),enabled=true,base=.6,plays=0,pauses=0;
const audio={paused:true,loop:true,volume:base,currentTime:0,playbackRate:1,play(){this.paused=false;plays++;return Promise.resolve()},pause(){this.paused=true;pauses++}};
const c=p.createAudioController(audio,{getBaseVolume:()=>base,isEnabled:()=>enabled,requestFrame:cb=>{queue.push(cb);return queue.length},cancelFrame:id=>cancelled.add(id),now:()=>1000});
c.play({restart:true});if(audio.loop||audio.volume!==.6||plays!==1)throw new Error('play');
c.finish(1000);if(!c.fading||audio.paused)throw new Error('fade start');
queue.shift()(3500);if(Math.abs(audio.volume-.3)>.0001||audio.paused)throw new Error('half fade');
queue.shift()(6000);if(audio.volume!==0||!audio.paused||c.fading)throw new Error('fade end');
if(base!==.6)throw new Error('stored volume');
c.reset();if(audio.volume!==.6||audio.currentTime!==0)throw new Error('reset');
enabled=false;c.play();if(plays!==1)throw new Error('disabled');
enabled=true;c.play();c.finish(7000);c.destroy();if(c.fading||!c.destroyed||!audio.paused)throw new Error('destroy');
"""
        self.run_node(script)
        for source in (self.replay, self.duel):
            self.assertIn("window.GRacePlayback.raceDelta", source)
            self.assertIn("audioController.finish()", source)
            self.assertIn("audio.loop=false", source)


if __name__ == "__main__":
    unittest.main()
