import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
EXPECTED_IDS = {
    "head-to-head-overview", "head-to-head-gap", "head-to-head-placement",
    "head-to-head-segments", "head-to-head-field-pacing", "head-to-head-course",
    "filters", "overview-kpis", "finish-distribution", "overview-segment-pace",
    "elevation-profile", "placement-engine", "target-time-simulator", "dnf-funnel",
    "segment-character", "advancement-ranking", "whole-race-pacing", "group-kpis",
    "group-pace-distribution", "group-retention", "group-insights", "age-class-lab",
    "age-class-pace", "pace-heatmap", "course-difficulty", "course-elevation-map",
    "course-distribution", "segment-lab", "time-thresholds", "field-flow",
    "race-intelligence", "standouts", "club-arena", "profile-summary",
    "profile-relative-insights", "profile-placement", "profile-pacing", "profile-splits",
    "runner-replay", "journey-gap", "journey-placement", "journey-pacing", "map-duel",
    "results-database", "data-principles",
    "goal-pace",
}


class AnalysisHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (ASSETS / "analysis-help-content.js").read_text(encoding="utf-8")
        cls.runtime = (ASSETS / "analysis-help.js").read_text(encoding="utf-8")
        cls.style = (ASSETS / "style.css").read_text(encoding="utf-8")
        cls.index = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.map_page = (DOCS / "karta.html").read_text(encoding="utf-8")

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        result = subprocess.run([node, "-e", body], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout.strip()

    def registry(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/analysis-help-content.js','utf8'));
console.log(JSON.stringify(window.GAnalysisHelpContent));
""")
        return json.loads(output)

    def test_registry_has_exact_reviewed_entries_and_quality(self):
        registry = self.registry()
        self.assertEqual(set(registry), EXPECTED_IDS)
        self.assertEqual(len(registry), 46)
        for help_id, entry in registry.items():
            self.assertTrue(entry.get("title", "").strip(), help_id)
            self.assertTrue(entry.get("html", "").strip(), help_id)
            self.assertTrue("<p" in entry["html"] or "<h4" in entry["html"], help_id)

    def test_registry_and_ui_manifest_have_identical_coverage(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['analysis-help-content.js','analysis-help.js'])vm.runInThisContext(fs.readFileSync('docs/assets/'+file,'utf8'));
console.log(JSON.stringify(window.GAnalysisHelp.validate()));
""")
        report = json.loads(output)
        self.assertEqual(set(report["registryIds"]), EXPECTED_IDS)
        self.assertEqual(set(report["usedIds"]), EXPECTED_IDS)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unknown"], [])

    def test_button_uses_one_fixed_inline_svg_and_accessible_native_markup(self):
        output = self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['analysis-help-content.js','analysis-help.js'])vm.runInThisContext(fs.readFileSync('docs/assets/'+file,'utf8'));
console.log(window.GAnalysisHelp.button('placement-engine'));
""")
        self.assertIn('<button type="button"', output)
        self.assertIn('class="analysis-help-button"', output)
        self.assertIn('data-analysis-help="placement-engine"', output)
        self.assertIn('aria-label="Information om ', output)
        self.assertIn('<svg class="analysis-help-icon" viewBox="0 0 24 24"', output)
        for forbidden in (">(i)<", ">i<", "ℹ", "ℹ️"):
            self.assertNotIn(forbidden, output)
        self.assertEqual(self.runtime.count("const ICON="), 1)
        self.assertNotIn("font-awesome", (self.index + self.map_page + self.runtime).lower())
        self.assertNotIn("material-icons", (self.index + self.map_page + self.runtime).lower())

    def test_runtime_contract_dialog_reuse_and_invalid_id(self):
        self.assertIn("document.getElementById('analysis-help-dialog')", self.runtime)
        self.assertEqual(self.runtime.count("document.createElement('dialog')"), 1)
        self.assertIn("event.target===dialog", self.runtime)
        self.assertIn("body.scrollTop=0", self.runtime)
        self.assertIn("previous?.isConnected", self.runtime)
        self.assertIn("event.target.closest?.('[data-analysis-help]')", self.runtime)
        self.assertIn("dialog.addEventListener('cancel'", self.runtime)
        self.run_node(r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['analysis-help-content.js','analysis-help.js'])vm.runInThisContext(fs.readFileSync('docs/assets/'+file,'utf8'));
const api=window.GAnalysisHelp;
if(!api.has('filters')||api.has('does-not-exist')||api.open('does-not-exist')!==false)process.exit(1);
if(!api.entry('filters')||typeof api.close!=='function'||typeof api.enhance!=='function')process.exit(2);
""")

    def test_assets_load_in_required_order_on_both_pages(self):
        for page in (self.index, self.map_page):
            self.assertLess(page.index("analysis-help-content.js"), page.index("analysis-help.js"))
            self.assertLess(page.index("analysis-help.js"), page.index("map-duel.js"))
        self.assertIn("analysis-help-content.js?v=20260908-goal-pace1", self.index)
        self.assertIn("analysis-help.js?v=20260908-goal-pace1", self.index)
        self.assertIn("analysis-help-content.js?v=20260907-head-to-head1", self.map_page)
        self.assertIn("analysis-help.js?v=20260907-head-to-head1", self.map_page)
        self.assertIn("style.css?v=20260908-goal-pace1", self.index)
        self.assertIn("style.css?v=20260907-favorites1", self.map_page)

    def test_dialog_css_is_scoped_responsive_and_motion_safe(self):
        for token in (
            ".analysis-help-dialog", "max-height:90dvh", ".analysis-help-body",
            "overflow-y:auto", ".analysis-help-button:focus-visible",
            "@media(max-width:620px)", "@media(prefers-reduced-motion:reduce)",
        ):
            self.assertIn(token, self.style)


if __name__ == "__main__":
    unittest.main()
