import json
import sqlite3
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "tools"
EXPECTED = {
    "individual-75-2026": ("individual-75", 2026, "2026-05-09", "course-v1", "individual"),
    "individual-35-2026": ("individual-35", 2026, "2026-05-09", "course-v1", "individual"),
    "relay-75-2026": ("relay-75", 2026, "2026-05-09", "course-v1", "relay"),
    "relay-35-2026": ("relay-35", 2026, "2026-05-09", "course-v1", "relay"),
}


class MultiyearRaceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        cls.web = json.loads((ROOT / "docs/data/results-2026.json").read_text(encoding="utf-8"))

    def test_config_declares_event_and_each_race_edition(self):
        self.assertEqual(self.config["event"]["event_key"], "gotaleden-stafett-ultra")
        self.assertNotIn("year", self.config["event"])
        self.assertNotIn("date", self.config["event"])
        actual = {
            race["race_key"]: (
                race["race_family"], race["year"], race["race_date"], race["course_version"], race["type"]
            )
            for race in self.config["races"]
        }
        self.assertEqual(actual, EXPECTED)

    def test_sqlite_and_web_export_match_config(self):
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as connection:
            rows = connection.execute(
                "SELECT race_key,event_key,race_family,year,race_date,course_version,race_type FROM races"
            ).fetchall()
        sqlite_catalog = {row[0]: row[1:] for row in rows}
        for key, expected in EXPECTED.items():
            family, year, race_date, course_version, race_type = expected
            contract = ("gotaleden-stafett-ultra", family, year, race_date, course_version, race_type)
            self.assertEqual(sqlite_catalog[key], contract)
            race = self.web["races"][key]
            self.assertEqual(
                (race["event_key"], race["race_family"], race["year"], race["race_date"], race["course_version"], race["type"]),
                contract,
            )

    def test_adapter_exposes_catalog_metadata_and_url_keys_stay_stable(self):
        script = r"""
const fs=require('fs'),vm=require('vm');
global.window=global;global.location={href:'https://example.test/'};
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
vm.runInThisContext(fs.readFileSync('docs/assets/app-state.js','utf8'));
const data=JSON.parse(fs.readFileSync('docs/data/results-2026.json','utf8'));
const route=JSON.parse(fs.readFileSync('docs/data/route.json','utf8'));
const elevation=JSON.parse(fs.readFileSync('docs/data/route-elevation-2026.json','utf8'));
const adapter=window.GDataAdapter.create(data,route,elevation);
const keys=Object.keys(data.races),catalog=Object.fromEntries(keys.map(key=>{const r=adapter.race(key);return[key,[r.key,r.eventKey,r.family,r.year,r.raceDate,r.courseVersion,r.type]]}));
const urls=Object.fromEntries(keys.map(key=>[key,window.GAppState.parse('?race='+key,{raceExists:value=>Boolean(adapter.race(value))}).raceKey]));
console.log(JSON.stringify({catalog,urls}));
"""
        result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        for key, expected in EXPECTED.items():
            family, year, race_date, course_version, race_type = expected
            self.assertEqual(
                payload["catalog"][key],
                [key, "gotaleden-stafett-ultra", family, year, race_date, course_version, race_type],
            )
            self.assertEqual(payload["urls"][key], key)

    def test_catalog_metadata_is_not_derived_from_race_names_or_distances(self):
        implementations = [
            ROOT / "tools/build_project_data.py",
            ROOT / "tools/build_official_data.py",
            ROOT / "docs/assets/data-adapter.js",
        ]
        metadata_names = ("race_family", "course_version", "raceFamily", "courseVersion", "raceDate")
        forbidden = (".includes(", ".match(", "RegExp(", "re.search(", "re.match(", "Göteborg", "Floda", "Alingsås", "35", "75")
        relevant = [
            line
            for path in implementations
            for line in path.read_text(encoding="utf-8").splitlines()
            if any(name in line for name in metadata_names)
        ]
        self.assertTrue(relevant)
        for line in relevant:
            self.assertFalse(any(token in line for token in forbidden), line)


if __name__ == "__main__":
    unittest.main()
