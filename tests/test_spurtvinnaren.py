import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SpurtvinnarenTests(unittest.TestCase):
    def test_module_uses_nolhaga_and_real_2026_data(self):
        node=os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script=r"""
const fs=require('fs'),vm=require('vm');
global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const sprint=require('./docs/assets/spurt-winners.js');
const data=JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
for(const key of ['individual-75-2026','individual-35-2026']){
  const race=adapter.race(key),control=sprint.lastTimingControl(race);
  if(control?.key!=='nolhaga')throw new Error(key+': expected Nolhaga');
  for(const sex of ['F','M']){
    const model=sprint.ranking(race,adapter,{sex});
    if(model.rows.length<5)throw new Error(key+': too few '+sex+' sprint rows');
    if(sprint.top(model.rows,5).length<5)throw new Error(key+': top five missing');
    if(model.rows.some((item,index)=>index&&item.sprintSeconds<model.rows[index-1].sprintSeconds))throw new Error(key+': order');
  }
}
if(sprint.lastTimingControl(adapter.race('relay-75-2026'))!==null)throw new Error('relay must not have sprint control');
const known=adapter.record('individual-75-2026:717'),profile=adapter.profile(known),nolhaga=profile.anchors.find(x=>x.checkpoint==='nolhaga');
const model=sprint.ranking(adapter.race('individual-75-2026'),adapter,{sex:known.sex});
const item=model.rows.find(x=>x.record.id===known.id);
if(!item||Math.abs(item.sprintSeconds-(known.finish_seconds-nolhaga.elapsedSeconds))>.0001)throw new Error('known sprint mismatch');
console.log(JSON.stringify({control:'nolhaga',knownSprint:item.sprintSeconds}));
"""
        completed=subprocess.run([node,"-e",script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(completed.returncode,0,completed.stderr or completed.stdout)

    def test_ui_contract(self):
        page=(ROOT/"docs/index.html").read_text(encoding="utf-8")
        css=(ROOT/"docs/assets/style.css").read_text(encoding="utf-8")
        app=(ROOT/"docs/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("SPURTVINNAREN",page)
        self.assertIn("Loppets spurtdrottning",page)
        self.assertIn("Loppets spurtkung",page)
        self.assertIn("spurt-winners.js?v=20260925-sprint1",page)
        for token in (".sprint-row.medal-1",".sprint-row.medal-2",".sprint-row.medal-3"):
            self.assertIn(token,css)
        self.assertIn("renderSprintWinners();renderHistory()",app)
        self.assertIn("root.hidden=Boolean(race.isTeam)",app)

if __name__=="__main__":
    unittest.main()
