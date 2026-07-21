import json
import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def normalize_club(value):
    return " ".join(str(value or "").split())


def club_key(value):
    return normalize_club(value).casefold()


class UiParityPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.style = (DOCS / "assets" / "style.css").read_text(encoding="utf-8")
        cls.app = (DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        cls.charts = (DOCS / "assets" / "charts.js").read_text(encoding="utf-8")
        cls.adapter = (DOCS / "assets" / "data-adapter.js").read_text(encoding="utf-8")
        cls.replay = (DOCS / "assets" / "runner-replay.js").read_text(encoding="utf-8")
        cls.interactive = (DOCS / "assets" / "interactive-analysis.js").read_text(encoding="utf-8")
        cls.results = json.loads(
            (DOCS / "data" / "results-2026.json").read_text(encoding="utf-8")
        )

    def test_gender_colors_use_the_exact_shared_tokens(self):
        self.assertIn("--male:#2563eb", self.style)
        self.assertIn("--female:#db2777", self.style)
        self.assertIn("SEX_COLORS=Object.freeze({M:'#2563eb',F:'#db2777'})", self.charts)
        self.assertIn("window.GCharts.SEX_COLORS[record.sex]", self.app)
        self.assertIn("window.GCharts.SEX_COLORS.F", self.interactive)
        self.assertIn("window.GCharts.SEX_COLORS.M", self.interactive)

    def test_club_normalization_is_trimmed_collapsed_and_case_insensitive(self):
        self.assertIn("trim().replace(/\\s+/g,' ')", self.adapter)
        self.assertIn("toLocaleLowerCase('sv')", self.adapter)
        self.assertIn("function clubGroups", self.adapter)
        self.assertIn("function clubRecords", self.adapter)
        self.assertEqual(club_key("  Borås   Löparklubb "), club_key("borås löparklubb"))

    def test_club_display_uses_the_most_frequent_original_variant(self):
        records = self.results["races"]["individual-75-2026"]["records"]
        variants = Counter(
            normalize_club(record.get("club"))
            for record in records
            if club_key(record.get("club")) == club_key("Borås löparklubb")
        )
        display = sorted(variants.items(), key=lambda item: (-item[1], item[0]))[0][0]
        self.assertEqual(display, "Borås Löparklubb")
        self.assertGreater(variants["Borås Löparklubb"], variants["Borås löparklubb"])
        self.assertIn("b[1]-a[1]", self.adapter)

    def test_boras_case_variants_merge_into_one_exact_key(self):
        records = self.results["races"]["individual-75-2026"]["records"]
        merged = [
            record
            for record in records
            if club_key(record.get("club")) == club_key("Borås Löparklubb")
        ]
        raw_variants = {normalize_club(record.get("club")) for record in merged}
        self.assertEqual(raw_variants, {"Borås Löparklubb", "Borås löparklubb"})
        self.assertEqual(len(merged), 4)
        self.assertIn("adapter.clubRecords(race.records,item.name)", self.interactive)

    def test_desktop_replay_has_live_map_and_analysis_columns(self):
        for token in (
            "replay-desktop-grid",
            "replay-live-panel",
            "replay-map-panel",
            "replay-analysis-panel",
            "desktop.dataset.replayDesktop",
        ):
            self.assertIn(token, self.replay + self.style)
        self.assertRegex(
            self.style,
            r"replay-desktop-grid\{display:grid;grid-template-columns:[^}]*minmax\(500px",
        )
        self.assertIn("width:min(1500px", self.style)

    def test_live_map_elevation_and_analysis_are_simultaneously_available(self):
        for token in (
            "data-replay-current-elevation",
            "data-replay-grade",
            "data-replay-remaining",
            "data-replay-ascent-remaining",
            "data-replay-map",
            "data-elevation-dock",
            "data-analysis-tab",
            "data-analysis-panel",
        ):
            self.assertIn(token, self.replay)
        self.assertIn("for(const selector of ['.replay-comparison-controls'", self.replay)
        self.assertIn("'[data-elevation-dock]'", self.replay)

    def test_profile_replay_is_visually_prioritized_before_secondary_analysis(self):
        self.assertIn("detailContent.insertBefore(container,secondaryInsights)", self.replay)
        self.assertIn("#detail-replay{order:4}", self.style)
        self.assertIn(".insight-cards{order:5}", self.style)
        self.assertIn(".detail-grid{order:6}", self.style)
        self.assertIn(".split-section{order:7}", self.style)

    def test_standout_rankings_include_graphical_progress_bars(self):
        self.assertIn('class="standout-bar"', self.interactive)
        self.assertIn("strength(Number(item.value))", self.interactive)
        self.assertIn(".standout-bar>span", self.style)
        self.assertRegex(self.style, r"standout-bar\{[^}]*height:7px")

    def test_readability_rules_raise_chart_table_and_control_sizes(self):
        self.assertIn(".chart text{font-size:12.5px}", self.style)
        self.assertIn("th,td{font-size:.88rem}", self.style)
        self.assertIn(".analysis-nav button{font-size:.8rem}", self.style)


if __name__ == "__main__":
    unittest.main()
