import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RelayClassModelTests(unittest.TestCase):
    def test_relay_class_meta_mapping_and_record_overrides(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = r"""
global.window={};require('vm').runInThisContext(require('fs').readFileSync('docs/assets/data-adapter.js','utf8'));
const meta=window.GDataAdapter.relayClassMeta;
const cases=[
  ['Män','men',true],['Kvinnor ','women',true],
  ['Mixed tävling - Minst hälften kvinnor','mixed',true],
  ['Mixed ej tävling - Fri fördelning','mixed',false]
];
for(const [name,family,ranked] of cases){const value=meta(name);if(value.family!==family||value.ranked!==ranked)throw new Error(name)}
const override=meta({class_name:'Män',class_is_ranked:false,class_competition_type:'non_competitive'});
if(override.ranked||override.competitionType!=='non_competitive')throw new Error('record truth not respected');
"""
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_relay_classes_are_normalized_without_changing_counts(self):
        data = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(len(race["records"]) for race in data["races"].values()), 607)
        self.assertEqual(len(data["splits"]), 4059)


if __name__ == "__main__":
    unittest.main()
