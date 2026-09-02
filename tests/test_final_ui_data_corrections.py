import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class FinalUiDataCorrectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.app = (DOCS / "assets/app.js").read_text(encoding="utf-8")
        cls.adapter = (DOCS / "assets/data-adapter.js").read_text(encoding="utf-8")
        cls.charts = (DOCS / "assets/charts.js").read_text(encoding="utf-8")
        cls.interactive = (DOCS / "assets/interactive-analysis.js").read_text(
            encoding="utf-8"
        )
        cls.style = (DOCS / "assets/style.css").read_text(encoding="utf-8")
        cls.results = json.loads(
            (DOCS / "data/results-2026.json").read_text(encoding="utf-8")
        )

    def test_global_club_autocomplete_is_wired_for_one_character_and_eight_results(self):
        self.assertIn('id="club-filter-suggestions"', self.html)
        self.assertIn(
            "setupClubPicker($('#club-filter'),$('#club-filter-suggestions')", self.app
        )
        self.assertIn("query.length<1", self.app)
        self.assertIn(".slice(0,8)", self.app)
        self.assertIn("<small>${count} deltagare</small>", self.app)

    def test_autocomplete_supports_exact_selection_keyboard_and_outside_click(self):
        for token in (
            "$('#club-filter').value=name;filtersChanged()",
            "if(event.key==='Escape')box.hidden=true",
            "if(event.key==='Enter')",
            "first.click()",
            "document.addEventListener('click'",
        ):
            self.assertIn(token, self.app)
        self.assertIn("$('#club-filter').oninput=filtersChanged", self.app)

    def test_boras_query_resolves_to_the_canonical_club(self):
        records = self.results["races"]["individual-75-2026"]["records"]
        matches = [
            record.get("club", "").strip()
            for record in records
            if " ".join((record.get("club") or "").split()).casefold()
            == "borås löparklubb"
        ]
        self.assertEqual(len(matches), 4)
        self.assertEqual(max(set(matches), key=matches.count), "Borås Löparklubb")
        self.assertIn("state.adapter.clubNames(race.records)", self.app)

    def test_histogram_sex_series_keep_exact_pink_and_blue(self):
        self.assertIn("SEX_COLORS=Object.freeze({M:'#2563eb',F:'#db2777'})", self.charts)
        self.assertIn('style="--series-color:${esc(', self.charts)
        self.assertIn(".series-bar{fill:var(--series-color)", self.style)
        self.assertNotIn('rx="2" fill="${series[seriesIndex].color', self.charts)

    def test_other_sex_views_use_the_same_shared_tokens(self):
        self.assertIn("color:window.GCharts.SEX_COLORS.F", self.interactive)
        self.assertIn("color:window.GCharts.SEX_COLORS.M", self.interactive)
        self.assertIn("color:sexMeta[record.sex]?.color", self.interactive)
        self.assertIn('style="--sex-color:${sexMeta[sex].color}', self.interactive)

    def test_chart_text_stays_readable_when_cards_narrow(self):
        self.assertIn(".chart{overflow-x:auto;overflow-y:hidden}", self.style)
        self.assertIn(".chart svg{min-width:760px}", self.style)
        self.assertIn(".chart text{font-size:14px}", self.style)
        self.assertIn(".checkpoint-label{font-size:13px!important}", self.style)
        self.assertIn(".legend span{font-size:.82rem}", self.style)

    def test_dnf_helper_uses_only_real_dnf_splits_and_analysis_checkpoints(self):
        for token in (
            "record.status==='DNF'",
            "for(const split of resultSplits(item))",
            "checkpoint?.analysis_boundary!==false",
            "groupMap.has(checkpoint.key)",
            "key:'before-first'",
        ):
            self.assertIn(token, self.adapter)
        self.assertNotIn("starterProfiles", self.interactive)
        self.assertIn(
            "adapter.dnfByLastAnalysisCheckpoint(records.filter(record=>record.sex===sex))",
            self.interactive,
        )
        self.assertIn("senast registrerade analyskontroll", self.html)

    def test_dnf_categories_sum_to_filtered_dnf_for_every_race(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the adapter integration test")
        script = r"""
const fs=require('fs'),vm=require('vm');
global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const adapter=window.GDataAdapter.create(
  JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8')),
  JSON.parse(fs.readFileSync('docs/data/route.json','utf8')),
  JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'))
);
const summary={};
for(const race of adapter.races.values()){
  const groups=adapter.dnfByLastAnalysisCheckpoint(race.records);
  const expected=race.records.filter(record=>record.status==='DNF');
  const grouped=groups.flatMap(group=>group.records);
  if(grouped.length!==expected.length)throw new Error(race.key+': DNF sum');
  if(grouped.some(record=>record.status!=='DNF'))throw new Error(race.key+': non-DNF');
  if(groups.some(group=>group.key==='nolhaga'))throw new Error(race.key+': Nolhaga');
  if(new Set(grouped.map(record=>record.id)).size!==expected.length)throw new Error(race.key+': duplicate');
  if(!race.isRelay)for(const sex of ['F','M']){
    const sexRecords=race.records.filter(record=>record.sex===sex);
    const sexGrouped=adapter.dnfByLastAnalysisCheckpoint(sexRecords).flatMap(group=>group.records);
    const sexExpected=sexRecords.filter(record=>record.status==='DNF');
    if(sexGrouped.length!==sexExpected.length)throw new Error(race.key+': '+sex+' DNF sum');
  }
  summary[race.key]=groups.map(group=>[group.key,group.count]);
}
const race=adapter.race('individual-35-2026');
const synthetic={...race.records[0],id:'synthetic-before-first',bib:'synthetic',status:'DNF'};
const before=adapter.dnfByLastAnalysisCheckpoint([synthetic]);
if(before.length!==1||before[0].key!=='before-first')throw new Error('before-first');
console.log(JSON.stringify(summary));
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["individual-75-2026"], [
            ["jonsered", 2], ["lerum", 2], ["floda", 5],
            ["tollered", 3], ["alingsas", 1],
        ])
        self.assertEqual(summary["individual-35-2026"], [
            ["tollered", 1], ["norsesund", 1],
        ])
        self.assertEqual(summary["relay-75-2026"], [["floda", 1]])
        self.assertEqual(summary["relay-35-2026"], [["alingsas", 1]])

    def test_dnf_sex_toggles_filter_separate_gender_rows(self):
        self.assertIn("activeDnfSexes=['F','M'].filter(sex=>sexViews.dnf[sex])", self.interactive)
        self.assertIn("data-dnf-sex", self.interactive)
        self.assertIn("#db2777", self.charts)
        self.assertIn("#2563eb", self.charts)

    def test_relay_modes_hide_all_club_ui_and_individual_modes_restore_it(self):
        for token in (
            "$('[data-target=\"clubs\"]').hidden=race.isRelay",
            "$('#clubs').hidden=race.isRelay",
            "$('#club-filter-field').hidden=race.isRelay",
            "$('.toolbar').classList.toggle('relay-toolbar',race.isRelay)",
            "club:race?.isRelay?'':$('#club-filter').value",
        ):
            self.assertIn(token, self.app)
        self.assertIn("if(!race||race.isRelay||query.length<1)", self.app)
        self.assertIn(".toolbar.relay-toolbar{grid-template-columns:", self.style)


if __name__ == "__main__":
    unittest.main()
