from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductCompletionTests(unittest.TestCase):
    def text(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_navigation_and_mobile_share_contract(self):
        html = self.text("docs/index.html")
        order = [
            'data-target="runner-lookup"', 'data-target="map-duel"',
            'data-target="overview"', 'data-target="statistics"',
            'data-target="gender"', 'data-target="age-analysis"',
            'data-target="segments"', 'data-target="clubs"',
            'data-target="results"',
        ]
        self.assertEqual(order, sorted(order, key=html.index))
        self.assertIn('aria-label="Dela aktuell vy">Dela</button>', html)
        self.assertIn('id="active-filter-summary"', html)

    def test_phase_a_edge_case_guards(self):
        app = self.text("docs/assets/app.js")
        replay = self.text("docs/assets/runner-replay.js")
        self.assertNotIn("cache:'no-store'", app)
        self.assertIn("requestAnimationFrame", app)
        self.assertIn("setTimeout(filtersChanged,150)", app)
        self.assertIn("aMissing?1:-1", app)
        self.assertIn("finishKey=profile.race.analysisCheckpoints.at(-1)?.key", replay)
        self.assertIn("profile.finish&&last.to?.checkpoint===finishKey", replay)
        self.assertIn("previous.to?.checkpoint!==current.from?.checkpoint", replay)

    def test_personal_summary_contract(self):
        adapter = self.text("docs/assets/data-adapter.js")
        module = self.text("docs/assets/personal-summary.js")
        html = self.text("docs/index.html")
        self.assertIn("function personalRaceSummary(value)", adapter)
        for field in ("fieldPercentile", "classPercentile", "relativeBest",
                      "relativeWeak", "largestPlacementGain",
                      "largestPlacementLoss", "lastAnalysisCheckpoint",
                      "coverage", "referenceLabel", "story"):
            self.assertIn(field, adapter)
        self.assertIn("navigator.share", module)
        self.assertIn("navigator.clipboard", module)
        self.assertIn('aria-live="polite"', module)
        self.assertIn("personal-summary.js?v=20260908-goal-pace1", html)


if __name__ == "__main__":
    unittest.main()
