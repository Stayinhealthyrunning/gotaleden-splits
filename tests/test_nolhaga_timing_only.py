import json
import os
import shutil
import sqlite3
import subprocess
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "docs/data/results-2026.json"


class NolhagaTimingOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        cls.results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        cls.splits = {
            (split["race_key"], str(split["bib"]), split["checkpoint"]): split
            for split in cls.results["splits"]
        }

    def test_nolhaga_metadata_is_explicit_and_consistent(self):
        configured = next(item for item in self.config["checkpoints"] if item["key"] == "nolhaga")
        self.assertEqual(
            {key: configured[key] for key in (
                "is_timing_point", "is_relay_exchange", "timing_only",
                "analysis_boundary", "replay_anchor", "speaker_checkpoint",
            )},
            {
                "is_timing_point": True,
                "is_relay_exchange": False,
                "timing_only": True,
                "analysis_boundary": False,
                "replay_anchor": True,
                "speaker_checkpoint": True,
            },
        )
        for race_key, checkpoints in self.results["checkpoints"].items():
            exported = next(item for item in checkpoints if item["key"] == "nolhaga")
            for key, value in configured.items():
                if key not in {"nominal_cumulative_km_75"}:
                    self.assertEqual(exported.get(key), value, (race_key, key))

    def test_official_analysis_boundaries_are_nine_and_four_segments(self):
        expected_75 = [
            "gothenburg", "skatas", "kasjon", "jonsered", "lerum", "floda",
            "tollered", "norsesund", "vastra_bodarna", "alingsas",
        ]
        expected_35 = ["floda", "tollered", "norsesund", "vastra_bodarna", "alingsas"]
        for race_key, checkpoints in self.results["checkpoints"].items():
            boundaries = [item["key"] for item in checkpoints if item["analysis_boundary"]]
            expected = expected_35 if "-35-" in race_key else expected_75
            self.assertEqual(boundaries, expected, race_key)
            self.assertEqual(len(boundaries) - 1, 4 if "-35-" in race_key else 9)

    def test_nolhaga_passages_and_source_counts_remain_intact(self):
        records = [record for race in self.results["races"].values() for record in race["records"]]
        self.assertEqual(len(records), 607)
        self.assertEqual(len(self.results["splits"]), 4059)
        self.assertEqual(
            {race_key: sum(split["race_key"] == race_key and split["checkpoint"] == "nolhaga" for split in self.results["splits"])
             for race_key in self.results["races"]},
            {
                "individual-75-2026": 203,
                "individual-35-2026": 127,
                "relay-75-2026": 107,
                "relay-35-2026": 44,
            },
        )

    def test_last_segment_uses_vastra_bodarna_and_finish_exactly(self):
        checked = 0
        for race_key, race in self.results["races"].items():
            checkpoint_map = {item["key"]: item for item in self.results["checkpoints"][race_key]}
            expected_distance = (
                checkpoint_map["alingsas"]["route_distance_km"]
                - checkpoint_map["vastra_bodarna"]["route_distance_km"]
            )
            for record in race["records"]:
                bib = str(record["bib"])
                vastra = self.splits.get((race_key, bib, "vastra_bodarna"))
                finish = self.splits.get((race_key, bib, "alingsas"))
                if not vastra or not finish:
                    continue
                elapsed = finish["elapsed_seconds"] - vastra["elapsed_seconds"]
                self.assertGreater(elapsed, 0)
                self.assertGreater(expected_distance, 0)
                if vastra.get("place_overall") is not None and finish.get("place_overall") is not None:
                    self.assertEqual(
                        vastra["place_overall"] - finish["place_overall"],
                        int(vastra["place_overall"]) - int(finish["place_overall"]),
                    )
                checked += 1
        self.assertEqual(checked, 486)

    def test_known_runner_proves_nolhaga_is_not_used_in_final_segment_math(self):
        key = "individual-75-2026"
        vastra = self.splits[(key, "717", "vastra_bodarna")]
        nolhaga = self.splits[(key, "717", "nolhaga")]
        finish = self.splits[(key, "717", "alingsas")]
        self.assertAlmostEqual(finish["elapsed_seconds"] - vastra["elapsed_seconds"], 2428.15, places=6)
        self.assertAlmostEqual(finish["elapsed_seconds"] - nolhaga["elapsed_seconds"], 47.76, places=6)
        self.assertNotEqual(
            finish["elapsed_seconds"] - vastra["elapsed_seconds"],
            finish["elapsed_seconds"] - nolhaga["elapsed_seconds"],
        )
        place_key = (key, "777")
        vastra_place = self.splits[(*place_key, "vastra_bodarna")]["place_overall"]
        nolhaga_place = self.splits[(*place_key, "nolhaga")]["place_overall"]
        finish_place = self.splits[(*place_key, "alingsas")]["place_overall"]
        self.assertEqual(vastra_place - finish_place, 1)
        self.assertEqual(nolhaga_place - finish_place, 0)

    def test_sqlite_persists_role_metadata_without_losing_raw_data(self):
        with closing(sqlite3.connect(ROOT / "data/gotaleden.sqlite")) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(checkpoints)")}
            self.assertTrue({"timing_only", "analysis_boundary", "replay_anchor", "speaker_checkpoint"} <= columns)
            rows = connection.execute(
                """SELECT timing_only, analysis_boundary, replay_anchor, speaker_checkpoint,
                          is_timing_point, is_relay_exchange
                   FROM checkpoints WHERE checkpoint_key='nolhaga'"""
            ).fetchall()
            self.assertEqual(rows, [(1, 0, 1, 1, 1, 0)] * 4)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM results").fetchone()[0], 607)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM splits WHERE is_finish_only_export=0").fetchone()[0],
                4059,
            )
            nolhaga_raw = connection.execute(
                """SELECT splits.raw_json FROM splits
                   JOIN checkpoints ON checkpoints.id=splits.checkpoint_id
                   WHERE checkpoints.checkpoint_key='nolhaga'"""
            ).fetchall()
            self.assertEqual(len(nolhaga_raw), 481)
            self.assertTrue(all(json.loads(row[0]) for row in nolhaga_raw))
            raw = json.loads(connection.execute("SELECT raw_json FROM results WHERE bib='717'").fetchone()[0])
            self.assertIn("public_contestant_api", raw)

    def test_public_code_contains_no_nolhaga_analytical_segment_label(self):
        public_files = list((ROOT / "docs/assets").glob("*.js"))
        joined = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
        for forbidden in ("Nolhaga–Mål", "Västra Bodarna–Nolhaga", "Nolhaga-Mål", "Västra Bodarna-Nolhaga"):
            self.assertNotIn(forbidden, joined)
        self.assertIn("race.analysisCheckpoints", joined)
        self.assertIn("speaker_checkpoint", joined)

    def test_all_public_analytical_consumers_use_analysis_boundaries(self):
        interactive = (ROOT / "docs/assets/interactive-analysis.js").read_text(encoding="utf-8")
        replay = (ROOT / "docs/assets/runner-replay.js").read_text(encoding="utf-8")
        duel = (ROOT / "docs/assets/map-duel.js").read_text(encoding="utf-8")
        charts = (ROOT / "docs/assets/charts.js").read_text(encoding="utf-8")
        app = (ROOT / "docs/assets/app.js").read_text(encoding="utf-8")
        self.assertNotIn("race.checkpoints.slice(1)", interactive)
        self.assertIn("race.analysisCheckpoints.slice(1)", interactive)
        self.assertIn("for(const checkpoint of race.analysisCheckpoints)", replay)
        self.assertIn("for(const checkpoint of race.analysisCheckpoints)", duel)
        self.assertIn("checkpoint.analysis_boundary!==false", charts)
        self.assertIn("checkpoints=race.analysisCheckpoints", app)
        self.assertIn("speakerpassering", app)
        self.assertIn("timing-only-checkpoint", replay)
        self.assertIn("timing-only-checkpoint", duel)

    def test_adapter_keeps_timing_interpolation_but_exposes_official_segment(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the adapter integration test")
        script = r"""
const fs=require('fs'),vm=require('vm');
global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const data=JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
for(const race of adapter.races.values()){
  const complete=race.records.map(record=>adapter.profile(record)).find(profile=>profile.complete&&profile.finish);
  const expected=race.key.includes('-35-')?4:9;
  if(!complete||complete.segments.length!==expected)throw new Error(`${race.key}: segment count`);
  const last=complete.segments.at(-1);
  if(last.name!=='Västra Bodarna–Mål')throw new Error(`${race.key}: ${last.name}`);
  if(Math.abs(last.time-(last.to.elapsedSeconds-last.from.elapsedSeconds))>.0001)throw new Error(`${race.key}: time`);
  if(Math.abs(last.distance-(last.to.distance-last.from.distance))>.0001)throw new Error(`${race.key}: distance`);
  if(last.combinedTimingPassages!==1||last.splitPlaceOverall!==null)throw new Error(`${race.key}: analytical span`);
  const nolhaga=complete.anchors.find(anchor=>anchor.checkpoint==='nolhaga');
  const finish=complete.anchors.find(anchor=>anchor.checkpoint==='alingsas');
  const state=adapter.stateAtTime(complete,(nolhaga.elapsedSeconds+finish.elapsedSeconds)/2);
  if(state.timingSegment.name!=='Nolhaga–Mål')throw new Error(`${race.key}: replay interpolation`);
  if(state.analysisInterval.name!=='Västra Bodarna–Mål')throw new Error(`${race.key}: public interval`);
  if(state.segment.name!=='Västra Bodarna–Mål')throw new Error(`${race.key}: public segment`);
  const syntheticData=structuredClone(data);
  syntheticData.splits=syntheticData.splits.filter(split=>!(split.race_key===race.key&&String(split.bib)===String(complete.record.bib)&&split.checkpoint==='alingsas'));
  const syntheticRecord=syntheticData.races[race.key].records.find(record=>String(record.bib)===String(complete.record.bib));
  syntheticRecord.status='DNF';syntheticRecord.finish_seconds=null;
  const synthetic=window.GDataAdapter.create(syntheticData,route,elevation);
  const partial=synthetic.profile(synthetic.record(`${race.key}:${complete.record.bib}`));
  const stopped=synthetic.stateAtTime(partial,partial.maxTime);
  if(stopped.segment!==null||stopped.analysisInterval.name!=='Västra Bodarna–Mål')throw new Error(`${race.key}: DNF fabrication`);
}
"""
        completed = subprocess.run(
            [node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
