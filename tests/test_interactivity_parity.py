import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class InteractivityParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        cls.adapter = (DOCS / "assets" / "data-adapter.js").read_text(encoding="utf-8")
        cls.replay = (DOCS / "assets" / "runner-replay.js").read_text(encoding="utf-8")
        cls.duel = (DOCS / "assets" / "map-duel.js").read_text(encoding="utf-8")
        cls.map_engine = (DOCS / "assets" / "map-engine.js").read_text(encoding="utf-8")
        cls.interactive = (DOCS / "assets" / "interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.results = json.loads((DOCS / "data" / "results-2026.json").read_text(encoding="utf-8"))

    def test_source_counts_are_unchanged(self):
        self.assertEqual(
            sum(len(race["records"]) for race in self.results["races"].values()), 607
        )
        self.assertEqual(len(self.results["splits"]), 4059)

    def test_reference_profiles_are_real_complete_and_cached(self):
        for token in (
            "MIN_REFERENCE_SIZE=5",
            "completeProfiles",
            "referenceProfiles",
            "referenceGap",
            "referenceCache",
            "cohortReference",
        ):
            self.assertIn(token, self.adapter)
        self.assertIn("candidate.complete", self.adapter)
        self.assertIn("adapter.referenceProfiles(record)", self.replay)
        self.assertNotIn("fabricated", self.replay.casefold())

        split_counts = Counter((split["race_key"], str(split["bib"])) for split in self.results["splits"])
        for race_key, race in self.results["races"].items():
            expected = len(self.results["checkpoints"][race_key]) - 1
            complete = [
                record
                for record in race["records"]
                if record["status"] == "FINISHED"
                and split_counts[(race_key, str(record["bib"]))] >= expected
            ]
            self.assertGreaterEqual(len(complete), 5, race_key)

    def test_field_class_and_sex_references_move_with_live_gap(self):
        for reference in ("field", "class", "sex"):
            self.assertRegex(self.replay, rf"\b{reference}\b")
        for token in (
            "data-comparison",
            "data-comparison-gap",
            "referenceGap",
            "timeAtDistance",
            "data-elevation-marker",
        ):
            self.assertIn(token, self.replay + self.adapter)
        self.assertIn("coincidesWith", self.adapter + self.replay)
        self.assertIn("localStorage", self.replay)

    def test_replay_map_elevation_and_seek_share_one_clock(self):
        for token in (
            "data-replay-time",
            "data-replay-slider",
            "data-elevation-hit",
            "timeAtDistance",
            "onSeek",
            ",segments,onSeek:",
        ):
            self.assertIn(token, self.replay + self.map_engine)
        self.assertIn("prefers-reduced-motion", self.replay)
        self.assertIn("placeExact", self.adapter)
        self.assertIn("senast kända", self.replay)

    def test_duel_supports_five_synchronized_colored_participants(self):
        self.assertEqual(self.duel.split("const palette=[", 1)[1].split("];", 1)[0].count("#"), 5)
        self.assertIn("state.duelIds.length>=5", self.app)
        for token in (
            "data-duel-elevation",
            "data-duel-elevation-marker",
            "data-duel-slider",
            "data-duel-board",
            "palette",
            "stopped",
            "finished",
        ):
            self.assertIn(token, self.duel)
        self.assertIn("audioEnabled:false", self.duel)

    def test_single_year_exploration_is_public_and_non_historical(self):
        self.assertIn("assets/interactive-analysis.js", self.index)
        for feature in (
            "data-sex-toggles",
            "data-scatter-reset",
            "gender-insights",
            "age-group-controls",
            "race-story",
            "standout-tabs",
            "club-pacing-extra",
        ):
            self.assertIn(feature, self.index)
        for behavior in (
            "renderSexExploration",
            "renderGenderInsights",
            "renderAge",
            "renderRaceStory",
            "renderStandouts",
            "renderClubExtras",
        ):
            self.assertIn(behavior, self.interactive)
        self.assertIn("inte officiella tävlingsklasser", self.index)

    def test_relay_class_analysis_preserves_team_level_semantics(self):
        self.assertIn("classGroups", self.interactive)
        self.assertIn("OFFICIELLA STAFETTKLASSER", self.interactive)
        self.assertIn("Inga lagmedlemmar kopplas till en specifik etapp", self.interactive)
        self.assertIn("if(race.isRelay){$$('[data-sex-toggles]')", self.interactive)
        self.assertIn("node.hidden=true", self.interactive)
        self.assertNotIn("relay_leg_assignments", self.index + self.app + self.interactive)

    def test_compact_share_state_restores_filters_profile_and_duel(self):
        for parameter in (
            "race",
            "section",
            "sex",
            "class",
            "status",
            "club",
            "unit",
            "runner",
            "duel",
        ):
            self.assertRegex(self.app, rf"(?:get|set)\('{parameter}'")
        self.assertIn("history.replaceState", self.app)
        self.assertIn("navigator.clipboard.writeText", self.app)

    def test_only_openstreetmap_layer_is_configured(self):
        self.assertIn("MAP_LAYERS", self.map_engine)
        self.assertIn("tile.openstreetmap.org", self.map_engine)
        self.assertNotRegex(self.map_engine.casefold(), r"mapbox|google|stadia|thunderforest")

    def test_no_medal_wall_or_gapminder_was_added(self):
        public = "\n".join((self.index, self.app, self.replay, self.duel, self.interactive)).casefold()
        for forbidden in ("medaljvägg", "medal wall", "gapminder", "historik – år mot år"):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
