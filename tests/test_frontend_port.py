import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class FrontendPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        cls.adapter = (DOCS / "assets" / "data-adapter.js").read_text(encoding="utf-8")
        cls.replay = (DOCS / "assets" / "runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (DOCS / "assets" / "map-duel.js").read_text(encoding="utf-8")
        cls.map_engine = (DOCS / "assets" / "map-engine.js").read_text(encoding="utf-8")
        cls.results = json.loads((DOCS / "data" / "results-2026.json").read_text(encoding="utf-8"))
        cls.route = json.loads((DOCS / "data" / "route.json").read_text(encoding="utf-8"))

    def test_four_race_modes_and_switcher_are_public(self):
        race_keys = {
            "individual-75-2026",
            "individual-35-2026",
            "relay-75-2026",
            "relay-35-2026",
        }
        self.assertEqual(set(self.results["races"]), race_keys)
        self.assertEqual(set(re.findall(r'data-race="([^"]+)"', self.index)), race_keys)
        self.assertIn("history.replaceState", self.app)
        self.assertIn("gotaleden-race", self.app)

    def test_runner_and_relay_team_detail_are_ported(self):
        self.assertIn("LÖPARANALYS", self.app)
        self.assertIn("LAGANALYS", self.app)
        self.assertIn("MELLANTIDER", self.app)
        self.assertIn("PACINGPROFIL", self.app)
        self.assertIn("Medlemslistan anger inte vem som sprang en viss etapp.", self.app)
        self.assertIn("data-runner-replay", self.replay)

    def test_map_duel_and_replay_use_shared_official_route_engine(self):
        self.assertIn("GMapEngine.create", self.replay)
        self.assertIn("GMapEngine.create", self.duel)
        self.assertIn("adapter.routeSlice", self.map_engine)
        self.assertIn("adapter.routePoint", self.map_engine)
        self.assertIn("data-duel-play", self.duel)
        self.assertIn("data-replay-play", self.replay)
        self.assertIn("Visa hela banan", self.map_engine)

    def test_leaflet_and_openstreetmap_are_the_primary_map_stack(self):
        self.assertIn("vendor/leaflet/leaflet.css?v=1.9.4", self.index)
        self.assertIn("vendor/leaflet/leaflet.js?v=1.9.4", self.index)
        leaflet_js = (DOCS / "vendor" / "leaflet" / "leaflet.js").read_text(encoding="utf-8")
        self.assertIn("Leaflet 1.9.4", leaflet_js)
        self.assertIn('version="1.9.4"', leaflet_js)
        self.assertIn("L.map(", self.map_engine)
        self.assertIn("L.tileLayer(layerConfig.url", self.map_engine)
        self.assertIn("tile.openstreetmap.org", self.map_engine)
        self.assertIn('data-map-engine="leaflet"', self.map_engine)
        self.assertIn("OpenStreetMap-bidragsgivare", self.map_engine)

    def test_leaflet_controls_markers_and_reset_contracts_are_present(self):
        self.assertIn("zoomControl:true", self.map_engine)
        self.assertIn("fitBounds", self.map_engine)
        self.assertIn("L.divIcon", self.map_engine)
        self.assertIn("L.marker", self.map_engine)
        self.assertIn("data-map-action=\"fit\"", self.map_engine)
        self.assertIn("data-replay-reset", self.replay)
        self.assertIn("data-replay-follow", self.replay)
        self.assertIn("data-duel-reset", self.duel)
        self.assertIn("data-duel-fit", self.duel)

    def test_dnf_stops_at_last_real_passage(self):
        split_keys = {(split["race_key"], split["bib"]) for split in self.results["splits"]}
        dnf_with_splits = [
            record
            for race in self.results["races"].values()
            for record in race["records"]
            if record["status"] == "DNF" and (race["race_key"], record["bib"]) in split_keys
        ]
        self.assertTrue(dnf_with_splits)
        self.assertIn("anchors.at(-1).distance", self.adapter)
        self.assertIn("time>=profileValue.maxTime&&!profileValue.finish", self.adapter)
        self.assertIn("stopped:state.stopped", self.replay)
        self.assertIn("stopped:item.state.stopped", self.duel)

    def test_audio_uses_central_source_and_requires_a_user_gesture(self):
        self.assertIn("assets/race-media.js", self.index)
        self.assertIn("media.audioSource?new Audio(media.audioSource):null", self.duel)
        self.assertIn("playAudio();lastFrame", self.duel)
        self.assertNotIn("autoplay", (self.index + self.duel).casefold())

    def test_35_km_route_slice_starts_at_floda(self):
        checkpoints = self.results["checkpoints"]["individual-35-2026"]
        self.assertEqual(checkpoints[0]["key"], "floda")
        self.assertAlmostEqual(checkpoints[0]["route_distance_km"], 41.333, places=3)
        self.assertEqual(checkpoints[-1]["key"], "alingsas")
        self.assertAlmostEqual(
            checkpoints[-1]["route_distance_km"], self.route["full_distance_km"], places=4
        )
        self.assertIn("startDistanceKm", self.adapter)
        self.assertIn("routeSlice", self.adapter)

    def test_single_year_ui_has_no_history_or_gapminder_sections(self):
        public_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in [DOCS / "index.html", *sorted((DOCS / "assets").glob("*.js"))]
        ).casefold()
        for forbidden in (
            "historik – år mot år",
            "historik - år mot år",
            "gapminder",
            "klassutveckling över år",
            "ultravasans utveckling genom åren",
        ):
            self.assertNotIn(forbidden, public_text)

    def test_public_relay_ui_has_no_runner_to_leg_claim(self):
        public_text = f"{self.index}\n{self.app}".casefold()
        for forbidden in ("runner-to-leg", "etapper och löpare", "verifierade etapper", "fleretappslöpare"):
            self.assertNotIn(forbidden, public_text)
        self.assertNotIn("relay_leg_assignments", public_text)

    def test_elevation_and_adapter_assets_are_wired(self):
        for asset in (
            "assets/data-adapter.js",
            "assets/map-engine.js",
            "assets/runner-replay.js",
            "assets/map-duel.js",
        ):
            self.assertIn(asset, self.index)
            self.assertTrue((DOCS / asset).exists())
        self.assertIn("route-elevation-2026.json", self.app)
        self.assertIn("GDataAdapter.create", self.app)
        self.assertIn("elevationSlice", self.adapter)

    def test_public_frontend_contains_no_reference_product_copy(self):
        public_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in [DOCS / "index.html", *sorted((DOCS / "assets").glob("*.js")), DOCS / "assets" / "style.css"]
        ).casefold()
        for forbidden in ("ultravasan", "vasaloppet", "sälen", "mora"):
            self.assertNotIn(forbidden, public_text)


if __name__ == "__main__":
    unittest.main()
