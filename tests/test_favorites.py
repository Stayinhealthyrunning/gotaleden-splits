import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


class FavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = (ASSETS / "favorites.js").read_text(encoding="utf-8")
        cls.app = (ASSETS / "app.js").read_text(encoding="utf-8")
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.style = (ASSETS / "style.css").read_text(encoding="utf-8")

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = "const fs=require('fs'),vm=require('vm');global.window={};vm.runInThisContext(fs.readFileSync('docs/assets/favorites.js','utf8'));" + body
        result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_empty_valid_invalid_duplicate_and_toggle_storage(self):
        out = self.run_node(r"""
const memory={value:null,getItem(){return this.value},setItem(k,v){this.value=v}};
const empty=window.GFavorites.create({storage:memory}),initial=empty.all();
empty.toggle('individual-75-2026:785');const added=empty.all();empty.toggle('individual-75-2026:785');const removed=empty.all();
memory.value='["individual-75-2026:785","individual-75-2026:785",4]';const valid=window.GFavorites.create({storage:memory}).all();
memory.value='{"id":"individual-75-2026:785"}';const wrongType=window.GFavorites.create({storage:memory}).all();
memory.value='{bad';const invalid=window.GFavorites.create({storage:memory}).all();
console.log(JSON.stringify({initial,added,removed,valid,wrongType,invalid,key:window.GFavorites.KEY}));
""")
        self.assertEqual(out["initial"], [])
        self.assertEqual(out["added"], ["individual-75-2026:785"])
        self.assertEqual(out["removed"], [])
        self.assertEqual(out["valid"], ["individual-75-2026:785"])
        self.assertEqual(out["wrongType"], [])
        self.assertEqual(out["invalid"], [])
        self.assertEqual(out["key"], "race-analysis:favorites-v1")

    def test_cross_race_filter_persistence_and_prune(self):
        out = self.run_node(r"""
const memory={value:'[]',getItem(){return this.value},setItem(k,v){this.value=v}};
const a=window.GFavorites.create({storage:memory});for(const id of ['individual-75-2026:785','individual-35-2026:1540','relay-75-2026:29','obsolete:1'])a.add(id);
const before=a.all(),i75=a.forRace('individual-75-2026');a.prune(['individual-75-2026:785','individual-35-2026:1540','relay-75-2026:29']);
const b=window.GFavorites.create({storage:memory});console.log(JSON.stringify({before,i75,after:b.all()}));
""")
        self.assertEqual(len(out["before"]), 4)
        self.assertEqual(out["i75"], ["individual-75-2026:785"])
        self.assertEqual(out["after"], ["individual-75-2026:785", "individual-35-2026:1540", "relay-75-2026:29"])

    def test_storage_exception_uses_session_memory(self):
        out = self.run_node(r"""
const broken={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};
const favorites=window.GFavorites.create({storage:broken});favorites.add('relay-35-2026:1002');console.log(JSON.stringify({all:favorites.all(),has:favorites.has('relay-35-2026:1002')}));
""")
        self.assertTrue(out["has"])
        self.assertEqual(out["all"], ["relay-35-2026:1002"])

    def test_single_svg_and_script_order(self):
        self.assertEqual(self.runtime.count("<svg"), 1)
        self.assertNotIn("★", self.runtime)
        self.assertNotIn("☆", self.runtime)
        self.assertIn('assets/favorites.js?v=20260907-favorites1', self.html)
        self.assertIn('assets/app.js?v=20260910-e1', self.html)
        self.assertLess(self.html.index("favorites.js"), self.html.index("app.js"))

    def test_results_profile_panel_accessibility_and_shared_selection(self):
        for token in ("favoriteToggle(record)", "favoriteToggle(record,{text:true})", 'id="favorites-list"', 'aria-live="polite"'):
            self.assertIn(token, self.app + self.html)
        for token in ('data-favorite-id=', 'aria-pressed=', 'aria-label=', 'record.id'):
            self.assertIn(token, self.app)
        for token in ("state.duelIds.includes(record.id)", "state.duelIds.push(record.id)", "state.duelIds=state.duelIds.filter", "renderDuel()", "Max 5 kan väljas till Kartduell."):
            self.assertIn(token, self.app)
        self.assertNotIn("favoriteComparisonIds", self.app)
        toggle_body = self.app.split("function toggleFavorite(record)", 1)[1].split("function syncProfileFavorite", 1)[0]
        self.assertNotIn("duelIds", toggle_body)
        self.assertIn(".favorites-panel", self.style)
        self.assertIn("@media(max-width:620px){.favorites-row", self.style)

    def test_relay_copy_and_help_registry_are_unchanged(self):
        self.assertIn("meta.shortLabel", self.app)
        self.assertIn("Ej tävling", self.app)
        self.assertIn("race.uiLabels?.saved", self.app)
        self.assertNotIn("record.sex", self.runtime)
        content = (ASSETS / "analysis-help-content.js").read_text(encoding="utf-8")
        self.assertEqual(content.count('"title":'), 51)


if __name__ == "__main__":
    unittest.main()
