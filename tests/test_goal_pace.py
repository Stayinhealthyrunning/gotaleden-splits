import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GoalPaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        cls.module = (ROOT / "docs/assets/goal-pace.js").read_text(encoding="utf-8")

    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/goal-pace.js','utf8'));
const segment=(index,distance,pace)=>({name:`P${index}–P${index+1}`,from:`p${index}`,to:`p${index+1}`,distanceKm:distance,pace:{median:pace}});
""" + body
        result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_normal_75_and_35_are_deterministic_and_exact(self):
        result = self.run_node(r"""
const race75={key:'individual-75-2026',section:'Individuellt 75',isRelay:false,analysisCheckpoints:Array(10)};
const race35={key:'individual-35-2026',section:'Individuellt 35',isRelay:false,analysisCheckpoints:Array(5)};
const p75={segments:Array.from({length:9},(_,i)=>segment(i,[4.5,10.5,7.5,10,9,8,12,6.5,10][i],390+i*18))};
const p35={segments:Array.from({length:4},(_,i)=>segment(i,[8,12,6.5,10][i],440+i*20))};
const a=window.GGoalPace.build(race75,p75,36000),again=window.GGoalPace.build(race75,p75,36000),b=window.GGoalPace.build(race35,p35,14400);
console.log(JSON.stringify({a,b,same:JSON.stringify(a)===JSON.stringify(again)}));
""")
        self.assertTrue(result["a"]["ok"])
        self.assertTrue(result["b"]["ok"])
        self.assertTrue(result["same"])
        self.assertEqual(result["a"]["segments"][-1]["cumulativeSeconds"], 36000)
        self.assertEqual(result["b"]["segments"][-1]["cumulativeSeconds"], 14400)
        self.assertEqual(len(result["a"]["segments"]), 9)
        self.assertEqual(len(result["b"]["segments"]), 4)

    def test_invalid_relay_incomplete_and_nonfinite_inputs_are_safe(self):
        result = self.run_node(r"""
const individual={key:'individual-75-2026',section:'Individuellt 75',isRelay:false,analysisCheckpoints:Array(10)};
const relay={...individual,key:'relay-75-2026',isRelay:true};
const incomplete={segments:Array.from({length:9},(_,i)=>segment(i,[4.5,10.5,7.5,10,9,8,12,6.5,10][i],i===4?null:400))};
console.log(JSON.stringify({invalid:window.GGoalPace.build(individual,incomplete,NaN),relay:window.GGoalPace.build(relay,incomplete,36000),missing:window.GGoalPace.build(individual,{segments:[]},36000),fallback:window.GGoalPace.build(individual,incomplete,36000)}));
""")
        for key in ("invalid", "relay", "missing"):
            value = result[key]
            self.assertFalse(value["ok"])
            self.assertNotIn("NaN", json.dumps(value))
            self.assertNotIn("Infinity", json.dumps(value))
        self.assertTrue(result["fallback"]["ok"])
        self.assertEqual(result["fallback"]["method"], "distance")
        self.assertEqual(result["fallback"]["segments"][-1]["cumulativeSeconds"], 36000)

    def test_ui_navigation_persistence_and_personal_integration(self):
        for token in ('data-target="goal-pace"', 'id="goal-pace"',
                      'goal-pace.js?v=20260908-goal-pace1'):
            self.assertIn(token, self.html)
        self.assertIn("gotaleden-goal-pace:${race.key}", self.module)
        self.assertIn("gotaleden:goal-pace", self.app)
        self.assertIn("selectedRace.isRelay", self.app)


if __name__ == "__main__":
    unittest.main()
