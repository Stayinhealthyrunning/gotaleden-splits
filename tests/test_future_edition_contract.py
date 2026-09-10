import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FutureEditionContractTests(unittest.TestCase):
    def run_node(self, body):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        setup = r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['docs/assets/data-adapter.js','docs/assets/course-data.js','docs/assets/history-engine.js','docs/assets/history-ui.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'));
const fixture=require('./tests/fixtures/future-edition.js').create(),requests=[];
const loader=window.GCourseData.create(fixture.data.courses,{fetchJson:async path=>{requests.push(path);return fixture.assets[path]}});
const assert=(condition,message)=>{if(!condition)throw new Error(message)};
"""
        completed = subprocess.run([node, "-e", setup + body], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_new_edition_activates_from_catalog_through_course_and_history(self):
        self.run_node(r"""
(async()=>{
  const alpha=await loader.load('route-alpha'),adapter=window.GDataAdapter.create(fixture.data,{'route-alpha':alpha}),engine=window.GHistoryEngine.create(adapter);
  assert(loader.has('route-alpha')&&!loader.has('route-beta'),'initial loading was not lazy');
  const beta=await loader.load('route-beta');adapter.registerCourse('route-beta',beta);
  await loader.load('route-beta');
  assert(requests.filter(path=>path.includes('route-beta')).length===2,'course assets were not cached');
  const future=adapter.race('solo-future'),before=adapter.race('solo-before'),incompatible=adapter.race('solo-incompatible');
  assert(future.family==='solo-family'&&future.year===2033&&future.raceDate==='2033-05-05'&&future.sourceEventKey==='source-future','edition metadata');
  assert(adapter.course(future).route.course_version==='route-beta','future course bundle');
  assert(adapter.courseComparability(before,future)==='compatible'&&adapter.courseComparability(before,incompatible)==='incomparable','explicit course comparability');
  assert(adapter.segmentComparability(fixture.data.courses['route-alpha'].segments[0],fixture.data.courses['route-beta'].segments[0])==='compatible','explicit segment comparability');
  const view=window.GHistoryUI.model({engine,adapter,raceKey:'solo-future',referenceRaceKey:'solo-before',segmentKey:'alpha-opening'});
  assert(JSON.stringify(view.editions.map(item=>item.raceKey))==='["solo-before","solo-future","solo-incompatible","solo-planned"]','catalog-driven future family');
  assert(view.observations[1].referenceComparability==='compatible'&&view.observations[2].referenceComparability==='incomparable','history comparability');
  assert(view.observations[3].availability.status==='planned'&&view.observations[3].records===null,'planned was represented as zero');
  assert(!view.editions.some(item=>item.year===2032),'missing year was fabricated');
  const teams=window.GHistoryUI.model({engine,adapter,raceKey:'team-future'});
  assert(JSON.stringify(teams.editions.map(item=>item.year))==='[2031,2033]'&&teams.race.isRelay,'family variation or relay failed');
})().catch(error=>{console.error(error);process.exit(1)});
""")

    def test_identity_and_state_contracts_remain_scoped(self):
        self.run_node(r"""
(async()=>{
  const alpha=await loader.load('route-alpha'),beta=await loader.load('route-beta'),gamma=await loader.load('route-gamma');
  const adapter=window.GDataAdapter.create(fixture.data,{'route-alpha':alpha,'route-beta':beta,'route-gamma':gamma}),engine=window.GHistoryEngine.create(adapter);
  const verified=engine.personHistory('verified-global-runner');
  assert(verified.appearanceCount===3,'verified provider identity did not repeat');
  assert(engine.personHistory('source-scoped-solo-before').appearanceCount===1&&engine.personHistory('source-scoped-solo-future').appearanceCount===1,'source scoped identities merged');
  assert(adapter.record('solo-before:2').source_result_id===adapter.record('solo-future:2').source_result_id,'fixture source scope');
  assert(engine.personHistory('local-solo-before').appearanceCount===1&&engine.personHistory('same-name-solo-before').appearanceCount===1,'local or name identity merged');
  assert(engine.personHistory('Shared Team').appearanceCount===0,'team name became a person');
  const exact=engine.compareAppearances('solo-before:1','solo-future:1'),blocked=engine.compareAppearances('solo-before:1','solo-incompatible:1');
  assert(exact.samePerson&&exact.finishTimeComparisonAllowed&&blocked.samePerson&&!blocked.finishTimeComparisonAllowed,'person comparability guard');
  assert(adapter.record('solo-future:1').id!=='solo-before:1'&&adapter.record('solo-future:1').raceKey==='solo-future','record ids are not race-scoped');
})().catch(error=>{console.error(error);process.exit(1)});
""")

    def test_real_public_export_remains_2026_only_and_unchanged(self):
        data = __import__("json").loads((ROOT / "docs/data/results.json").read_text(encoding="utf-8"))
        expected = {
            "individual-75-2026": 274,
            "individual-35-2026": 163,
            "relay-75-2026": 121,
            "relay-35-2026": 49,
        }
        self.assertEqual(set(data["races"]), set(expected))
        self.assertEqual(sum(len(data["races"][key]["records"]) for key in expected), 607)
        self.assertEqual(len(data["splits"]), 4059)
        for key, count in expected.items():
            self.assertEqual(len(data["races"][key]["records"]), count)
            self.assertEqual(data["races"][key]["year"], 2026)

    def test_generic_activation_paths_do_not_know_fixture_or_event_values(self):
        generic = [ROOT / "docs/assets/course-data.js", ROOT / "docs/assets/history-engine.js", ROOT / "docs/assets/history-ui.js"]
        for path in generic:
            source = path.read_text(encoding="utf-8")
            for forbidden in ("solo-future", "route-beta", "2031", "2033", "Gotaleden", "Göteborg", "Floda", "Alingsås", "EQ Timing"):
                self.assertNotIn(forbidden, source, f"{path.name}: {forbidden}")
        adapter = (ROOT / "docs/assets/data-adapter.js").read_text(encoding="utf-8")
        adapter_activation = re.search(r"function course\(value\).*?function record\(id\)", adapter, re.S)
        self.assertIsNotNone(adapter_activation)
        app = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        activation = re.search(r"async function ensureCourse\(key\).*?\n  function switchRace", app, re.S)
        selector = re.search(r"function renderRaceSelector\(\).*?\n  function switchRace", app, re.S)
        self.assertIsNotNone(activation)
        self.assertIsNotNone(selector)
        for source in (adapter_activation.group(), activation.group(), selector.group()):
            for forbidden in ("solo-future", "route-beta", "2031", "2033", "2026", "35", "75", "Gotaleden", "Göteborg", "Floda", "Alingsås", "EQ Timing"):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
