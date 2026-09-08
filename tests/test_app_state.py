import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppStateTests(unittest.TestCase):
    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = """
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/app-state.js','utf8'));
""" + body
        result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_parse_validates_race_and_normalizes_query_state(self):
        result = self.run_node("""
const exists=key=>['individual-75-2026','individual-35-2026'].includes(key);
const valid=window.GAppState.parse('?race=individual-35-2026&section=goal-pace&unit=speed&sex=F&runner=42&duel=1,2,3,4,5,6',{raceExists:exists,storedRace:'individual-75-2026'});
const fallback=window.GAppState.parse('?race=unknown&section=unknown',{raceExists:exists,storedRace:'individual-75-2026'});
console.log(JSON.stringify({valid:{...valid,params:undefined},fallback:{...fallback,params:undefined}}));
""")
        self.assertEqual(result["valid"]["raceKey"], "individual-35-2026")
        self.assertEqual(result["valid"]["activeSection"], "goal-pace")
        self.assertEqual(result["valid"]["unit"], "speed")
        self.assertEqual(result["valid"]["duelBibs"], ["1", "2", "3", "4", "5"])
        self.assertEqual(result["fallback"]["raceKey"], "individual-75-2026")
        self.assertEqual(result["fallback"]["activeSection"], "runner-lookup")

    def test_url_roundtrip_keeps_only_canonical_state(self):
        result = self.run_node("""
const href=window.GAppState.url('https://example.test/?stale=yes',{raceKey:'individual-75-2026',activeSection:'goal-pace',unit:'speed',selectedRecordId:'individual-75-2026:717',duelIds:['individual-75-2026:717','individual-75-2026:610']},{sex:'F',className:'Kvinnor',status:'FINISHED',club:'Herkules'});
const parsed=window.GAppState.parse(new URL(href).search,{raceExists:()=>true});
console.log(JSON.stringify({href,parsed:{...parsed,params:undefined}}));
""")
        self.assertNotIn("stale", result["href"])
        self.assertEqual(result["parsed"]["runnerBib"], "717")
        self.assertEqual(result["parsed"]["duelBibs"], ["717", "610"])
        self.assertEqual(result["parsed"]["filters"]["club"], "Herkules")

    def test_visible_section_ignores_hidden_sections(self):
        result = self.run_node("""
const sections=[{id:'runner-lookup',hidden:false,offsetTop:0},{id:'goal-pace',hidden:true,offsetTop:100},{id:'overview',hidden:false,offsetTop:200}];
console.log(JSON.stringify({early:window.GAppState.visibleSection(sections,150),late:window.GAppState.visibleSection(sections,250)}));
""")
        self.assertEqual(result, {"early": "runner-lookup", "late": "overview"})


if __name__ == "__main__":
    unittest.main()
