import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from course_versions import (  # noqa: E402
    CourseConfigError,
    _fingerprint_material,
    _gpx_geometry_digest,
    _material_definition,
    checkpoint_catalog,
    course_comparability,
    race_course_geometry,
    resolve_all_courses,
    resolve_course_version,
    segment_comparability,
)


def synthetic_config(route_name="tests/fixtures/course/route.gpx"):
    checkpoints = [
        {"key": "alpha", "name": "Alpha", "nominal_distance_km": 0},
        {"key": "middle", "name": "Middle", "nominal_distance_km": 1},
        {"key": "omega", "name": "Omega", "nominal_distance_km": 2},
    ]
    course = {
        "event_key": "portable-event",
        "route_source": route_name,
        "checkpoint_catalog": "catalog-a",
        "anchors": [
            {"key": "start", "checkpoint": "alpha", "route_position": "start"},
            {"key": "mid", "checkpoint": "middle", "coordinate": {"lat": 0, "lon": 0.01}, "max_snap_distance_m": 5},
            {"key": "finish", "checkpoint": "omega", "route_position": "end"},
        ],
        "segments": [
            {"key": "alpha-middle", "from": "alpha", "to": "middle"},
            {"key": "middle-omega", "from": "middle", "to": "omega"},
        ],
    }
    race = lambda key, version, family="family-a", start="alpha": {
        "race_key": key, "race_family": family, "course_version": version,
        "route_range": {"from": start, "to": "omega"},
        "checkpoint_keys": [start, "omega"] if start == "middle" else ["alpha", "middle", "omega"],
    }
    return {
        "checkpoint_catalogs": {"catalog-a": checkpoints},
        "course_versions": {"course-a": course},
        "races": [race("edition-a", "course-a"), race("edition-b", "course-a")],
    }


class CourseVersionCoreTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT
        self.config = synthetic_config()

    def test_shared_course_and_neutral_partial_route_range(self):
        courses = resolve_all_courses(self.config, self.root)
        self.assertEqual(list(courses), ["course-a"])
        first = race_course_geometry(self.config["races"][0], courses["course-a"])
        second = race_course_geometry(self.config["races"][1], courses["course-a"])
        self.assertEqual(first, second)
        partial = copy.deepcopy(self.config["races"][0])
        partial.update({"route_range": {"from": "middle", "to": "omega"}, "checkpoint_keys": ["middle", "omega"]})
        geometry = race_course_geometry(partial, courses["course-a"])
        self.assertAlmostEqual(geometry["start_route_distance_km"], 1.1119, places=3)
        self.assertEqual([item["key"] for item in geometry["checkpoints"]], ["middle", "omega"])

    def test_whole_course_and_segment_comparability_are_explicit(self):
        base = resolve_course_version(self.config, self.root, "course-a")
        courses = {"course-a": base, "course-b": {**base, "key": "course-b", "whole_course_comparison_group": None}}
        race_a = {"race_family": "family-a", "course_version": "course-a"}
        self.assertEqual(course_comparability(race_a, dict(race_a), courses), "exact")
        self.assertEqual(course_comparability(race_a, {**race_a, "course_version": "course-b"}, courses), "incomparable")
        courses["course-a"]["whole_course_comparison_group"] = "verified-group"
        courses["course-b"]["whole_course_comparison_group"] = "verified-group"
        self.assertEqual(course_comparability(race_a, {**race_a, "course_version": "course-b"}, courses), "compatible")
        self.assertEqual(segment_comparability({"course_version": "course-a", "key": "s"}, {"course_version": "course-b", "key": "s"}), "incomparable")
        self.assertEqual(segment_comparability({"course_version": "course-a", "key": "s", "comparison_key": "verified-s"}, {"course_version": "course-b", "key": "other", "comparison_key": "verified-s"}), "compatible")

    def test_immutable_fingerprint_detects_changed_geometry(self):
        resolved = resolve_course_version(self.config, self.root, "course-a")
        self.config["course_versions"]["course-a"]["expected_fingerprint"] = resolved["fingerprint"]
        self.config["checkpoint_catalogs"]["catalog-a"][1]["nominal_distance_km"] = 1.1
        with self.assertRaisesRegex(CourseConfigError, "fingerprint changed"):
            resolve_course_version(self.config, self.root, "course-a")

    def test_fingerprint_is_line_ending_independent_but_geometry_sensitive(self):
        fixture = (ROOT / "tests/fixtures/course/route.gpx").read_bytes()
        course = self.config["course_versions"]["course-a"]
        checkpoints = checkpoint_catalog(self.config, course)
        fingerprint = lambda raw: _fingerprint_material(_material_definition(
            self.root, "course-a", course, checkpoints,
            {"route_source": _gpx_geometry_digest(raw), "elevation_reference_source": None},
        ))
        lf = fingerprint(fixture.replace(b"\r\n", b"\n"))
        self.assertEqual(lf, fingerprint(fixture.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")))
        self.assertNotEqual(lf, fingerprint(fixture.replace(b'lon="0.02"', b'lon="0.03"')))

    def test_frontend_loader_selects_assets_and_caches_each_version(self):
        node = os.environ.get("GOTALEDEN_NODE") or shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        script = r"""
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('docs/assets/course-data.js','utf8'));
vm.runInThisContext(fs.readFileSync('docs/assets/data-adapter.js','utf8'));
const calls=[],files={
 'a-route':{points:[[1,1,0,0],[1,2,0,2]],full_distance_km:2},'a-elevation':{points:[]},
 'b-route':{points:[[2,1,0,0],[2,2,0,2]],full_distance_km:2},'b-elevation':{points:[]}};
const catalog={'course-a':{assets:{route:'a-route',elevation:'a-elevation'}},'course-b':{assets:{route:'b-route',elevation:'b-elevation'}}};
(async()=>{const loader=window.GCourseData.create(catalog,{fetchJson:async path=>{calls.push(path);return files[path]}}),a=await loader.load('course-a');await loader.load('course-a');const b=await loader.load('course-b'),data={courses:catalog,races:{a:{course_version:'course-a',race_family:'f',year:1,type:'individual',gpx_distance_km:2,records:[]},b:{course_version:'course-b',race_family:'f',year:2,type:'individual',gpx_distance_km:2,records:[]}},checkpoints:{a:[{key:'s',route_distance_km:0},{key:'f',route_distance_km:2}],b:[{key:'s',route_distance_km:0},{key:'f',route_distance_km:2}]}};const adapter=window.GDataAdapter.create(data,{'course-a':a,'course-b':b});console.log(JSON.stringify({calls,latA:adapter.routeSlice('a')[0][0],latB:adapter.routeSlice('b')[0][0],asset:adapter.courseAsset('b','route')}))})().catch(error=>{console.error(error);process.exit(1)});
"""
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value, {"calls": ["a-route", "a-elevation", "b-route", "b-elevation"], "latA": 1, "latB": 2, "asset": "b-route"})

    def test_real_2026_course_geometry_and_compatibility_aliases_match(self):
        config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        course = resolve_course_version(config, ROOT, "course-v1")
        geometries = {race["race_key"]: race_course_geometry(race, course) for race in config["races"]}
        self.assertAlmostEqual(course["route"]["full_distance_km"], 77.1194, places=4)
        self.assertAlmostEqual(geometries["individual-35-2026"]["gpx_distance_km"], 35.7864, places=4)
        self.assertEqual((ROOT / "docs/data/route.json").read_bytes(), (ROOT / "docs/data/courses/course-v1/route.json").read_bytes())
        self.assertEqual((ROOT / "docs/data/route-elevation-2026.json").read_bytes(), (ROOT / "docs/data/courses/course-v1/elevation.json").read_bytes())
        payload = json.loads((ROOT / "docs/data/results.json").read_text(encoding="utf-8"))
        with sqlite3.connect(ROOT / "data/gotaleden.sqlite") as connection:
            sqlite_course = connection.execute("SELECT fingerprint,route_asset,elevation_asset FROM course_versions WHERE course_version='course-v1'").fetchone()
        self.assertEqual(sqlite_course, (
            course["fingerprint"], "data/courses/course-v1/route.json", "data/courses/course-v1/elevation.json",
        ))
        self.assertEqual(payload["courses"]["course-v1"]["fingerprint"], course["fingerprint"])

    def test_generic_course_code_contains_no_event_geometry_special_cases(self):
        source = (TOOLS / "course_versions.py").read_text(encoding="utf-8").casefold()
        for token in ("gotaleden", "gothenburg", "floda", "41.5", "78.0", "2026"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
