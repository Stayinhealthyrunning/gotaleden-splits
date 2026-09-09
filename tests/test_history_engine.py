import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryEngineTests(unittest.TestCase):
    def run_node(self, body, *, real=False):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        setup = r"""
const fs=require('fs'),vm=require('vm');global.window={};
for(const file of ['docs/assets/data-adapter.js','docs/assets/history-engine.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'));
function synthetic(){
  vm.runInThisContext(fs.readFileSync('tests/fixtures/history/multiyear.js','utf8'));
  const fixture=window.GHistoryFixture.create(),adapter=window.GDataAdapter.create(fixture.data,fixture.route,fixture.elevation);
  return{fixture,adapter,engine:window.GHistoryEngine.create(adapter)};
}
function production(){
  const data=JSON.parse(fs.readFileSync('docs/data/results.json','utf8'));
  const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
  const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
  const adapter=window.GDataAdapter.create(data,route,elevation);
  return{data,adapter,engine:window.GHistoryEngine.create(adapter)};
}
const assert=(condition,message)=>{if(!condition)throw new Error(message)};
"""
        script = setup + ("const {data,adapter,engine}=production();\n" if real else "const {fixture,adapter,engine}=synthetic();\n") + body
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_family_timelines_are_chronological_without_fabricated_years(self):
        self.run_node(r"""
const a=engine.editions('family-a'),b=engine.editions('family-b');
assert(JSON.stringify(a.map(item=>item.year))==='[2024,2025,2026,2027,2028]','family A order');
assert(JSON.stringify(b.map(item=>item.year))==='[2025,2027]','missing year was fabricated');
assert(!b.some(item=>item.year===2026),'missing year must stay missing');
const planned=engine.editionSummary('family-a-2028-planned');
assert(planned.availability.status==='planned'&&planned.records===null&&planned.finishTime.reason==='edition_planned','planned edition metrics');
""")

    def test_edition_summary_reuses_status_distribution_and_filter_semantics(self):
        self.run_node(r"""
const summary=engine.editionSummary('family-a-2024');
assert(summary.records===8&&summary.starters===7&&summary.finishers===6&&summary.dnf===1&&summary.dns===1,'status counts');
assert(summary.finishRate===6/7&&summary.dnfRate===1/7,'rates');
assert(summary.finishTime.available&&summary.finishTime.sampleSize===6&&summary.finishTime.median===1035,'finish distribution');
const filtered=engine.editionSummary('family-a-2024',{sex:'F',class:'Women',club:'north'});
assert(filtered.records===2&&filtered.finishers===2&&filtered.dnf===0,'shared filters');
fixture.data.races['family-a-2024'].analyzable=false;
fixture.data.race_catalog['family-a-2024'].analyzable=false;
const disabledAdapter=window.GDataAdapter.create(fixture.data,fixture.route,fixture.elevation);
const disabled=window.GHistoryEngine.create(disabledAdapter).editionSummary('family-a-2024');
assert(disabled.records===8&&disabled.availability.status==='available_not_analyzable'&&!disabled.finishTime.available,'available non-analyzable');
""")

    def test_edition_comparison_separates_participation_from_course_performance(self):
        self.run_node(r"""
const exact=engine.compareEditions('family-a-2024','family-a-2025');
const compatible=engine.compareEditions('family-a-2024','family-a-2026');
const blocked=engine.compareEditions('family-a-2024','family-a-2027');
assert(exact.comparability==='exact'&&exact.performance.medianFinishSeconds.delta===40,'exact');
assert(compatible.comparability==='compatible'&&compatible.performance.available,'compatible');
assert(blocked.comparability==='incomparable'&&!blocked.performance.available&&blocked.performance.reason==='course_incomparable','incomparable performance');
assert(blocked.participation.records.available&&blocked.participation.records.delta===0,'participation remains comparable');
""")

    def test_family_series_uses_explicit_reference_and_availability_reasons(self):
        self.run_node(r"""
const neutral=engine.familySeries('family-a');
assert(neutral.observations.every(item=>item.referenceComparability===null&&item.comparablePerformance.reason==='reference_not_requested'),'no implicit reference');
const series=engine.familySeries('family-a',{referenceRaceKey:'family-a-2024'}),byYear=Object.fromEntries(series.observations.map(item=>[item.year,item]));
assert(byYear[2024].referenceComparability==='exact'&&byYear[2025].referenceComparability==='exact','exact reference');
assert(byYear[2026].referenceComparability==='compatible'&&byYear[2026].comparablePerformance.available,'compatible reference');
assert(byYear[2027].referenceComparability==='incomparable'&&byYear[2027].comparablePerformance.reason==='course_incomparable','blocked reference');
assert(!byYear[2028].comparablePerformance.available&&byYear[2028].comparablePerformance.reason==='edition_planned','planned reference');
""")

    def test_segment_series_requires_explicit_identity_not_display_name(self):
        self.run_node(r"""
const opening=engine.segmentSeries('family-a',{referenceRaceKey:'family-a-2024',segmentKey:'opening-a'}),open=Object.fromEntries(opening.observations.map(item=>[item.year,item]));
assert(open[2024].comparability==='exact'&&open[2025].comparability==='exact','same version segment');
assert(open[2026].comparability==='compatible'&&open[2026].pace.available,'mapped segment');
assert(open[2027].comparability==='incomparable'&&!open[2027].pace.available,'unmapped course');
const closing=engine.segmentSeries('family-a',{referenceRaceKey:'family-a-2024',segmentKey:'closing-a'}),close=Object.fromEntries(closing.observations.map(item=>[item.year,item]));
assert(close[2025].comparability==='exact','same version closing');
assert(close[2026].comparability==='incomparable'&&close[2026].pace.reason==='segment_incomparable','same name must not map');
""")

    def test_segment_samples_use_real_analysis_boundaries_and_complete_cohort(self):
        self.run_node(r"""
const race=adapter.race('family-a-2024');
assert(race.checkpoints.length===4&&race.analysisCheckpoints.length===3,'timing point boundary leak');
const group=adapter.segmentGroupDistribution(race,()=>true);
assert(group.count===5&&group.segments.length===2,'stable complete cohort');
assert(group.segments.every(segment=>segment.n===5&&!segment.name.includes('Timing only')),'fabricated timing segment');
const observation=engine.segmentSeries('family-a',{referenceRaceKey:'family-a-2024',segmentKey:'opening-a'}).observations[0];
assert(observation.sampleSize===5&&observation.cohortSize===5,'missing split entered segment sample');
const relay=engine.segmentSeries('family-b',{referenceRaceKey:'family-b-2025',segmentKey:'opening-a'}).observations;
assert(relay.length===2&&relay.every(item=>item.comparability==='exact'&&item.sampleSize===5),'relay segment history');
""")

    def test_person_history_keeps_identity_and_course_comparability_separate(self):
        self.run_node(r"""
const history=engine.personHistory('person-provider-global');
assert(history.appearanceCount===4&&JSON.stringify(history.years)==='[2024,2025,2026,2027]','provider identity history');
assert(history.appearances.every(item=>item.identityStatus==='verified'&&item.identityScope==='provider'),'identity metadata');
const exact=engine.compareAppearances('family-a-2024:1','family-a-2025:1');
const blocked=engine.compareAppearances('family-a-2024:1','family-a-2027:1');
assert(exact.samePerson&&exact.wholeCourseComparability==='exact'&&exact.finishTimeComparisonAllowed,'same person exact');
assert(blocked.samePerson&&blocked.wholeCourseComparability==='incomparable'&&!blocked.finishTimeComparisonAllowed,'same person incompatible');
""")

    def test_scoped_local_name_and_team_values_never_create_repeat_identity(self):
        self.run_node(r"""
assert(engine.personHistory('person-source-2024').appearanceCount===1&&engine.personHistory('person-source-2025').appearanceCount===1,'source-event merge');
const sourceA=adapter.record('family-a-2024:2'),sourceB=adapter.record('family-a-2025:2');
assert(sourceA.source_result_id===sourceB.source_result_id&&sourceA.personKey!==sourceB.personKey&&sourceA.identityScope==='source_event'&&sourceB.identityScope==='source_event','same scoped external id merged across events');
assert(engine.personHistory('person-local-family-a-2024').appearanceCount===1&&engine.personHistory('person-local-family-a-2025').appearanceCount===1,'local merge');
assert(engine.personHistory('person-same-name-family-a-2024').appearanceCount===1&&engine.personHistory('person-same-name-family-a-2025').appearanceCount===1,'name merge');
const repeats=engine.repeatParticipants();
assert(repeats.length===1&&repeats[0].personKey==='person-provider-global','repeat identities');
assert(engine.personHistory('Same Team').appearanceCount===0,'team-name identity');
""")

    def test_real_export_has_four_single_edition_families_and_unchanged_metrics(self):
        self.run_node(r"""
const expected={'individual-75-2026':[274,206,13,55],'individual-35-2026':[163,127,2,34],'relay-75-2026':[121,109,1,11],'relay-35-2026':[49,45,1,3]};
assert(engine.families().length===4,'family count');
let total=0;
for(const [key,values] of Object.entries(expected)){
  const summary=engine.editionSummary(key);total+=summary.records;
  assert(JSON.stringify([summary.records,summary.finishers,summary.dnf,summary.dns])===JSON.stringify(values),key+' metrics');
  assert(engine.editions(summary.family).length===1,'fabricated edition '+key);
  assert(engine.compareEditions(key,key).comparability==='exact','self comparison '+key);
}
assert(total===607&&data.splits.length===4059,'canonical data parity');
assert(engine.repeatParticipants().length===0,'false cross-year repeats');
""", real=True)

    def test_history_core_is_provider_event_year_and_distance_neutral(self):
        source = (ROOT / "docs/assets/history-engine.js").read_text(encoding="utf-8")
        for forbidden in ("Gotaleden", "Ultravasan", "Österlen", "Floda", "Göteborg", "EQ Timing"):
            self.assertNotIn(forbidden, source)
        self.assertIsNone(re.search(r"\b(?:2026|35|75)\b", source))
        index = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertNotIn("history-engine.js", index)


if __name__ == "__main__":
    unittest.main()
