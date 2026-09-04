import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class StandaloneMapDuelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.map_html = (DOCS / "karta.html").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")
        cls.map_page = (ASSETS / "map-page.js").read_text(encoding="utf-8")
        cls.map_css = (ASSETS / "map-page.css").read_text(encoding="utf-8")
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")
        cls.results = json.loads((DOCS / "data/results-2026.json").read_text(encoding="utf-8"))

    def run_node(self, script):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for standalone map integration tests")
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_main_page_is_a_launcher_without_inline_map(self):
        self.assertIn('id="open-map-duel" type="button" disabled', self.index)
        self.assertIn("Öppna individuell karta", self.app)
        self.assertIn("Öppna lagkarta", self.app)
        self.assertIn("Öppna Kartduell ·", self.app)
        self.assertIn("state.duelIds.length>=5", self.app)
        self.assertIn("window.open(url,'_blank')", self.app)
        self.assertIn("win.opener=null", self.app)
        self.assertIn("else location.href=url", self.app)
        self.assertNotIn("GMapDuel.create", self.app)
        self.assertNotIn('id="map-duel-stage"', self.index)

    def test_standalone_assets_and_direct_url_helpers_execute(self):
        script = r"""
const fs=require('fs'),vm=require('vm');
const data=JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
global.window={};global.document={getElementById:()=>null};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
vm.runInThisContext(fs.readFileSync('docs/assets/map-duel.js','utf8'));
vm.runInThisContext(fs.readFileSync('docs/assets/map-page.js','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
for(const key of ['individual-75-2026','individual-35-2026','relay-75-2026','relay-35-2026']){
  const record=adapter.race(key).records[0];
  const selected=window.GMapPage.selectionFrom('?race='+key+'&entries='+encodeURIComponent(record.bib),adapter);
  if(selected.error||selected.records[0].id!==record.id)throw new Error('selection '+key);
  const url=window.GMapDuel.buildUrl(key,[record.bib],123);
  if(!url.includes('race='+key)||!url.includes('entries='+encodeURIComponent(record.bib))||!url.includes('t=123'))throw new Error('url '+key);
}
if(window.GMapPage.modeFor({isRelay:false},1)!=='INDIVIDUELL KARTA')throw new Error('individual mode');
if(window.GMapPage.modeFor({isRelay:true},1)!=='LAGKARTA')throw new Error('relay mode');
if(window.GMapPage.modeFor({isRelay:false},2)!=='KARTDUELL')throw new Error('duel mode');
if(window.GMapPage.fmtTime(0)!=='0:00:00'||window.GMapPage.fmtTime(15272)!=='4:14:32')throw new Error('clock format');
const timed=window.GMapPage.selectionFrom('?race=individual-75-2026&entries='+encodeURIComponent(adapter.race('individual-75-2026').records[0].bib)+'&t=15272',adapter);
if(timed.time!==15272)throw new Error('initial clock time');
if(!window.GMapPage.selectionFrom('?race=individual-75-2026&entries=1,2,3,4,5,6',adapter).error)throw new Error('max five');
"""
        self.run_node(script)
        for asset in ("map-duel.js", "map-page.js"):
            self.assertIn(f'assets/{asset}?v=20260903-standalone-map2', self.map_html)
        self.assertIn('assets/map-page.css?v=20260903-standalone-map2', self.map_html)

    def test_standalone_clock_is_wired_to_every_runtime_time_change(self):
        self.assertIn('id="map-clock"', self.map_html)
        self.assertIn('id="map-clock-max"', self.map_html)
        self.assertIn("onTimeChange:time=>syncClock(time)", self.map_page)
        self.assertIn("syncClock(runtime.getTime(),runtime.getMaxTime())", self.map_page)
        self.assertIn("initialTime:selection.time", self.map_page)
        self.assertIn("function reset(){stop();time=0", self.duel)
        self.assertIn("time=clamp(value,0,maxTime);render(forceCamera)", self.duel)

    def test_standalone_exposes_one_music_and_one_fit_control(self):
        self.assertIn('id="map-music"', self.map_html)
        self.assertIn('.map-page [data-duel-audio]', self.map_css)
        self.assertIn('.map-page [data-map-action="fit"]', self.map_css)
        self.assertNotIn('.map-page [data-duel-volume]', self.map_css)
        self.assertNotIn('.map-page [data-duel-fit]', self.map_css)
        self.assertIn("[data-duel-fit]').onclick=()=>{camera.value='overview';map.fit()}", self.duel)

    def test_music_transport_contract_is_explicit(self):
        self.assertIn("audio.loop=true", self.duel)
        self.assertIn("function finishAnimation(){stop({pauseAudio:false})}", self.duel)
        self.assertIn("else if(playing||time>=maxTime)playAudio()", self.duel)
        self.assertIn("if(pauseAudio)audio?.pause()", self.duel)
        self.assertIn("if(playing){stop();return}", self.duel)
        self.assertIn("if(time>=maxTime){time=0;if(audio)audio.currentTime=0}", self.duel)
        self.assertIn("function reset(){stop();time=0", self.duel)
        self.assertIn("audio.playbackRate=1", self.duel)
        self.assertNotIn("audio.playbackRate=Number(speed", self.duel)
        self.assertIn("const BASE_PLAYBACK_SECONDS=180", self.duel)
        self.assertIn("maxTime/BASE_PLAYBACK_SECONDS", self.duel)

    def test_adapter_preserves_dnf_nolhaga_and_35_km_math(self):
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const adapter=window.GDataAdapter.create(
 JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8')),
 JSON.parse(fs.readFileSync('docs/data/route.json','utf8')),
 JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8')));
for(const key of ['individual-35-2026','relay-35-2026']){
 const race=adapter.race(key);if(race.checkpoints[0].name!=='Floda'||race.startDistanceKm<=0)throw new Error('35 start');
 const progress=(race.startDistanceKm-race.startDistanceKm)/(race.endDistanceKm-race.startDistanceKm);if(progress!==0)throw new Error('35 progress');
}
const race=adapter.race('individual-75-2026'),nolhaga=race.checkpointMap.get('nolhaga');
if(!nolhaga.timing_only||!nolhaga.speaker_checkpoint||!nolhaga.replay_anchor||nolhaga.analysis_boundary!==false)throw new Error('nolhaga flags');
if(adapter.analysisIntervalAtDistance(race,nolhaga.route_distance_km+.01).name!=='Västra Bodarna–Mål')throw new Error('nolhaga analysis interval');
const dnf=[...adapter.records.values()].find(record=>record.status==='DNF'&&adapter.profile(record).anchors.length>1&&adapter.profile(record).maxDistance<adapter.profile(record).race.endDistanceKm);
if(!dnf)throw new Error('no DNF fixture');const profile=adapter.profile(dnf),state=adapter.stateAtTime(profile,profile.maxTime+1000);
if(!state.stopped||state.finished||state.distance!==profile.maxDistance||state.distance>=profile.race.endDistanceKm)throw new Error('DNF stop');
"""
        self.run_node(script)
        segments = {"individual-75-2026": 9, "individual-35-2026": 4, "relay-75-2026": 9, "relay-35-2026": 4}
        self.assertEqual(sum(split["checkpoint"] == "nolhaga" for split in self.results["splits"]), 481)
        for race_key, count in segments.items():
            checkpoints = self.results["checkpoints"][race_key]
            boundaries = [item for item in checkpoints if item["analysis_boundary"] is not False]
            self.assertEqual(len(boundaries) - 1, count)
            names = [f"{left['name']}–{right['name']}" for left, right in zip(boundaries, boundaries[1:])]
            self.assertNotIn("Nolhaga–Mål", names)
            self.assertNotIn("Västra Bodarna–Nolhaga", names)

    def test_relay_cards_are_team_only_and_ranked_missing_place_is_not_unranked(self):
        self.assertIn("adapter.relayClassMeta(record)", self.duel)
        self.assertIn("meta.ranked?'':' · Ej tävling'", self.duel)
        self.assertIn("item.state.classPlace?` · klass #${item.state.classPlace}`:' · klass –'", self.duel)
        self.assertNotIn("record.sex", self.duel)
        self.assertNotIn("team_members", self.duel)
        self.assertNotIn("aktuell löpare", self.duel.casefold())

    def test_runner_replay_contract_remains_separate(self):
        self.assertIn("audio.loop=true", self.replay)
        self.assertIn("window.GRunnerReplay", self.replay)
        self.assertNotIn("map-page", self.replay)


if __name__ == "__main__":
    unittest.main()
