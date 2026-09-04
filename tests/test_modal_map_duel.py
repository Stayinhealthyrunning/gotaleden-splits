import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class ModalMapDuelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.css = (ASSETS / "style.css").read_text(encoding="utf-8")
        cls.duel = (ASSETS / "map-duel.js").read_text(encoding="utf-8")
        cls.replay = (ASSETS / "runner-replay.js").read_text(encoding="utf-8")
        cls.standalone = (DOCS / "karta.html").read_text(encoding="utf-8")

    def test_selection_contract_requires_two_and_caps_at_five(self):
        self.assertIn("state.duelIds.length>=5", self.app)
        self.assertIn("button.disabled=count<2", self.app)
        for copy in (
            "Välj minst två deltagare",
            "Välj minst två lag",
            "Välj en deltagare till",
            "Välj ett lag till",
            "Öppna Kartduell · ${count}",
        ):
            self.assertIn(copy, self.app)
        self.assertIn("records.length<2||records.length>5", self.app)

    def test_modal_is_a_distinct_visible_host_before_runtime_creation(self):
        self.assertIn('<dialog id="detail-dialog"', self.html)
        self.assertIn('<dialog id="duel-dialog"', self.html)
        self.assertIn('id="duel-dialog-content"', self.html)
        self.assertIn("dialog.showModal();state.duel=window.GMapDuel.create", self.app)
        self.assertLess(self.app.index("dialog.showModal();state.duel"), self.app.index("requestAnimationFrame(()=>state.duel?.fit())"))
        self.assertNotIn("window.open", self.app)
        self.assertNotIn("location.href=", self.app)

    def test_close_destroys_runtime_audio_and_map_and_reopen_creates_new_runtime(self):
        self.assertIn("addEventListener('close',destroyDuel)", self.app)
        self.assertIn("function destroyDuel(){state.duel?.destroy();state.duel=null", self.app)
        self.assertIn("destroyDuel();$('#duel-dialog-race')", self.app)
        self.assertIn("destroy(){stop();destroyed=true;if(audio){audio.currentTime=0;audio.removeAttribute('src');audio.load()}map.destroy()", self.duel)

    def test_share_uses_standalone_url_without_navigating(self):
        self.assertIn("window.GMapDuel.buildUrl(state.raceKey,records,state.duel.getTime())", self.app)
        self.assertIn("navigator.clipboard.writeText(url)", self.app)
        self.assertIn("Länk kopierad", self.app)
        self.assertIn("assets/map-page.js", self.standalone)

    def test_modal_layout_is_large_responsive_and_has_backdrop(self):
        for token in (
            ".duel-dialog{width:min(96vw,1600px);height:min(94dvh,920px)",
            ".duel-dialog::backdrop",
            ".duel-dialog .duel-shell",
            ".duel-dialog .leaflet-map",
            "@media(max-width:760px){.duel-dialog{width:100vw;height:100dvh",
            ".duel-dialog .duel-board.collapsed",
        ):
            self.assertIn(token, self.css)

    def test_both_playbacks_keep_music_after_finish_but_destroy_stops_it(self):
        for source in (self.duel, self.replay):
            self.assertIn("audio.loop=true", source)
            self.assertIn("audio.playbackRate=1", source)
            self.assertIn("function stop({pauseAudio=true}={})", source)
            self.assertIn("function finishAnimation(){stop({pauseAudio:false})}", source)
            self.assertIn("else if(playing||time>=maxTime)playAudio()", source)
            self.assertIn("if(audio)audio.currentTime=0", source)
            self.assertIn("audio.removeAttribute('src');audio.load()", source)
        self.assertIn("const BASE_PLAYBACK_SECONDS=180", self.duel)


if __name__ == "__main__":
    unittest.main()
