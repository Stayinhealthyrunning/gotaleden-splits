import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RelaySexMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        cls.replay = (ROOT / "docs/assets/runner-replay.js").read_text(encoding="utf-8")

    def test_sex_filter_is_kept_for_individual_and_hidden_ignored_for_relay(self):
        self.assertIn('id="sex-filter-field">Kön<select id="sex-filter"', self.html)
        self.assertIn("$('#sex-filter-field').hidden=race.isRelay", self.app)
        self.assertIn("sex:race?.isRelay?'':$('#sex-filter').value", self.app)
        self.assertIn("$('#sex-filter').onchange=filtersChanged", self.app)

    def test_placement_scatter_uses_neutral_relay_and_sex_colors_for_individual(self):
        self.assertIn("race.isRelay?{color:meta.color}", self.app)
        self.assertIn("{sex:record.sex,color:window.GCharts.SEX_COLORS[record.sex]", self.app)

    def test_replay_omits_sex_reference_only_for_relay(self):
        self.assertIn("sex:{label:'Mitt kön'", self.replay)
        self.assertIn("!(record.isRelay&&key==='sex')", self.replay)
        self.assertIn("runner-replay.js?v=20260904-journey1", self.html)
        self.assertIn("app.js?v=20260904-journey1", self.html)


if __name__ == "__main__":
    unittest.main()
