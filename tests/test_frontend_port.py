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
