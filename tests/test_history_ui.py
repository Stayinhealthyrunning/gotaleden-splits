import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryUiTests(unittest.TestCase):
    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        setup = r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['docs/assets/data-adapter.js','docs/assets/history-engine.js','docs/assets/history-ui.js','tests/fixtures/history/multiyear.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'));
const fixture=window.GHistoryFixture.create(),adapter=window.GDataAdapter.create(fixture.data,fixture.route,fixture.elevation),engine=window.GHistoryEngine.create(adapter);
const assert=(condition,message)=>{if(!condition)throw new Error(message)};
"""
        completed = subprocess.run([node, "-e", setup + body], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_view_model_resolves_real_editions_without_fabricating_years(self):
        self.run_node(r"""
const view=window.GHistoryUI.model({engine,adapter,raceKey:'family-a-2024'});
assert(view.race.family==='family-a','family');
assert(JSON.stringify(view.editions.map(item=>item.year))==='[2024,2025,2026,2027,2028]','edition years');
assert(view.reference==='family-a-2024','current edition is default reference');
assert(view.observations.at(-1).availability.status==='planned'&&view.observations.at(-1).records===null,'planned is not zero');
assert(view.analyzable.length===4,'only actual analyzable editions');
""")

    def test_view_model_preserves_course_and_segment_comparability(self):
        self.run_node(r"""
const view=window.GHistoryUI.model({engine,adapter,raceKey:'family-a-2024',referenceRaceKey:'family-a-2024',segmentKey:'opening-a'});
const byYear=Object.fromEntries(view.observations.map(item=>[item.year,item]));
assert(byYear[2025].referenceComparability==='exact','exact course');
assert(byYear[2026].referenceComparability==='compatible','compatible course');
assert(byYear[2027].referenceComparability==='incomparable'&&!byYear[2027].comparablePerformance.available,'blocked performance');
const segments=Object.fromEntries(view.segmentSeries.observations.map(item=>[item.year,item]));
assert(segments[2026].comparability==='compatible'&&segments[2026].pace.available,'mapped segment');
assert(segments[2027].comparability==='incomparable'&&!segments[2027].pace.available,'unmapped segment');
assert(view.repeats.length===1&&view.repeats[0].personKey==='person-provider-global','verified repeat only');
""")

    def test_relay_view_model_keeps_team_history_at_edition_level(self):
        self.run_node(r"""
const view=window.GHistoryUI.model({engine,adapter,raceKey:'family-b-2025'});
assert(view.race.isRelay&&view.observations.length===2,'relay editions');
assert(view.repeats.length===0,'team names never create repeat people');
assert(view.segmentSeries.observations.every(item=>item.sampleSize===5),'relay cohort semantics');
""")


if __name__ == "__main__":
    unittest.main()
