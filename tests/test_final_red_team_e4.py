import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FinalRedTeamE4Tests(unittest.TestCase):
    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['docs/assets/data-adapter.js','docs/assets/history-engine.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'));
const assert=(condition,message)=>{if(!condition)throw new Error(message)};
""" + body
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_dns_observations_remain_raw_but_never_create_race_progress(self):
        self.run_node(r"""
const data=JSON.parse(fs.readFileSync('docs/data/results.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
for(const bib of ['782','519']){
  const record=adapter.record(`individual-75-2026:${bib}`),profile=adapter.profile(record);
  assert(record.status==='DNS'&&adapter.resultSplits(record).length===1,`${bib}: raw DNS evidence changed`);
  assert(profile.anchors.length===1&&profile.timingSegments.length===0&&profile.segments.length===0,`${bib}: DNS acquired race progress`);
  assert(profile.maxDistance===profile.race.startDistanceKm,`${bib}: DNS moved from the start`);
}
""")

    def test_every_team_format_is_excluded_from_person_history_and_sex_filtering(self):
        self.run_node(r"""
vm.runInThisContext(fs.readFileSync('tests/fixtures/alternate-event.js','utf8'));
const fixture=window.GAlternateEventFixture.create(),team=fixture.data.races['duo-long-a'];
team.records[0].person_key='poison-team-identity';team.records[0].identity_status='verified';team.records[0].identity_scope='provider';team.records[0].sex='F';
const bundles={};for(const [key,entry] of Object.entries(fixture.data.courses))bundles[key]={route:fixture.assets[entry.assets.route],elevation:fixture.assets[entry.assets.elevation]};
const adapter=window.GDataAdapter.create(fixture.data,bundles),engine=window.GHistoryEngine.create(adapter),race=adapter.race('duo-long-a');
assert(race.isTeam&&!race.isRelay,'fixture must be a non-relay team');
assert(engine.personHistory('poison-team-identity').appearanceCount===0,'team became person history');
assert(engine.editionSummary(race.key,{sex:'F'}).records===race.records.length,'sex filter leaked into team history');
""")

    def test_generic_app_state_has_no_event_specific_default_race(self):
        self.run_node(r"""
vm.runInThisContext(fs.readFileSync('docs/assets/app-state.js','utf8'));
const state=window.GAppState.parse('?race=unknown',{raceExists:()=>false});
assert(state.raceKey===null,'generic state invented an event-specific race');
""")


if __name__ == "__main__":
    unittest.main()
