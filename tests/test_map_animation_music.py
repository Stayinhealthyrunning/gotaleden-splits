import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class MapAnimationMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.media = (ASSETS / "race-media.js").read_text(encoding="utf-8")
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")
        cls.results = json.loads(
            (DOCS / "data/results-2026.json").read_text(encoding="utf-8")
        )

    def test_music_asset_exists_and_has_content(self):
        music = ASSETS / "gotaleden-ultra.mp3"
        self.assertTrue(music.is_file())
        self.assertGreater(music.stat().st_size, 1_000_000)

    def test_index_loads_one_central_media_config_before_both_animations(self):
        media_index = self.html.index('assets/race-media.js')
        self.assertLess(self.html.index('assets/data-index.js'), media_index)
        self.assertLess(media_index, self.html.index('assets/runner-replay.js'))
        self.assertLess(media_index, self.html.index('assets/map-duel.js'))
        sources = sum(
            path.read_text(encoding="utf-8").count("gotaleden-ultra.mp3")
            for path in ASSETS.glob("*.js")
        )
        self.assertEqual(sources, 1)
        self.assertIn("assets/gotaleden-ultra.mp3?v=20260901-music1", self.media)

    def test_media_defaults_and_gotaleden_storage_keys_execute(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for media configuration tests")
        script = r"""
const fs=require('fs'),vm=require('vm'),store={};
const context={window:{},localStorage:{getItem:key=>Object.hasOwn(store,key)?store[key]:null,setItem:(key,value)=>store[key]=String(value)}};
vm.runInNewContext(fs.readFileSync('docs/assets/race-media.js','utf8'),context);
const media=context.window.GotaledenMedia;
if(media.audioEnabled!==true)throw new Error('music must default on');
if(media.volume!==.35)throw new Error('default volume');
media.setEnabled(false);media.setVolume(.6);
if(store['gotaleden-music-enabled']!=='false')throw new Error('enabled key');
if(store['gotaleden-music-volume']!=='0.6')throw new Error('volume key');
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertNotIn("ultravasan-music", self.media + self.replay + self.duel)

    def test_runner_replay_audio_controls_and_transport_are_wired(self):
        for token in (
            "data-replay-audio",
            "data-replay-volume",
            'aria-label="Musikvolym"',
            "function playAudio()",
            "playAudio();lastFrame",
            "audio?.pause()",
            "if(audio)audio.currentTime=0",
            "audio.removeAttribute('src');audio.load()",
            "audio.loop=true",
        ):
            self.assertIn(token, self.replay)
        self.assertIn("audio.play().catch(()=>showAudioNote", self.replay)
        self.assertIn("function stop({pauseAudio=true}={})", self.replay)
        self.assertIn("function finishAnimation(){stop({pauseAudio:false})}", self.replay)
        self.assertIn("if(time>=maxTime)finishAnimation()", self.replay)
        self.assertIn("else if(playing||time>=maxTime)playAudio()", self.replay)

    def test_map_duel_reuses_shared_state_and_syncs_its_button(self):
        for token in (
            "media=window.GotaledenMedia||{}",
            "initialAudioEnabled=Boolean(media.audioEnabled&&audio)",
            "syncAudioButton();playButton.onclick=toggle",
            "media.setEnabled?media.setEnabled(!audioEnabled)",
            "data-duel-volume",
            "if(audio)audio.currentTime=0",
            "audio.removeAttribute('src');audio.load()",
            "audio.loop=true",
        ):
            self.assertIn(token, self.duel)
        self.assertIn("audio.play().catch(()=>showAudioNote", self.duel)
        self.assertIn("else if(playing||time>=maxTime)playAudio()", self.duel)

    def test_audio_never_follows_map_playback_speed(self):
        self.assertIn("audio.playbackRate=1", self.replay)
        self.assertIn("audio.playbackRate=1", self.duel)
        self.assertNotIn("audio.playbackRate=Number(speed", self.replay + self.duel)
        self.assertNotIn("audio.playbackRate=speed", self.replay + self.duel)

    def test_no_autoplay_attribute_or_ultravasan_music_is_referenced(self):
        public = self.html + self.media + self.replay + self.duel
        self.assertNotIn("autoplay", public.casefold())
        self.assertNotIn("Eldspar-till-Mora.mp3", public)
        self.assertNotIn("Ultravasan-45.mp3", public)

    def test_data_and_course_invariants_are_unchanged(self):
        self.assertEqual(
            sum(len(race["records"]) for race in self.results["races"].values()), 607
        )
        self.assertEqual(len(self.results["splits"]), 4059)
        expected_segments = {
            "individual-75-2026": 9,
            "individual-35-2026": 4,
            "relay-75-2026": 9,
            "relay-35-2026": 4,
        }
        for race_key, expected in expected_segments.items():
            checkpoints = self.results["checkpoints"][race_key]
            nolhaga = next(item for item in checkpoints if item["key"] == "nolhaga")
            self.assertFalse(nolhaga["analysis_boundary"])
            self.assertEqual(
                sum(item["analysis_boundary"] is not False for item in checkpoints) - 1,
                expected,
            )


if __name__ == "__main__":
    unittest.main()
