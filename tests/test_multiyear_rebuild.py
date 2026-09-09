import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from source_bindings import (  # noqa: E402
    SourceBindingError,
    dispatch_source_groups,
    group_source_bindings,
    race_catalog,
    resolve_source_bindings,
    web_race_catalog,
)


def synthetic_config():
    return {
        "event": {"event_key": "portable-event", "name": "Portable event"},
        "source_events": {
            "source-alpha": {
                "provider": "eqtiming",
                "race_bindings": {"long": {"source_race_name": "Long"}},
            },
            "source-beta": {
                "provider": "eqtiming",
                "race_bindings": {
                    "long": {"source_race_name": "Long"},
                    "short": {"source_race_name": "Short"},
                },
            },
        },
        "races": [
            {
                "race_key": "edition-a", "race_family": "family-long", "year": 2031,
                "section": "Long A", "type": "individual", "data_status": "available", "course_version": "course-a",
                "route_range": {"from": "start", "to": "finish"}, "checkpoint_keys": ["start", "finish"],
                "source_binding": {"source_event": "source-alpha", "race": "long"},
            },
            {
                "race_key": "edition-b", "race_family": "family-long", "year": 2032,
                "section": "Long B", "type": "individual", "data_status": "available", "course_version": "course-a",
                "route_range": {"from": "start", "to": "finish"}, "checkpoint_keys": ["start", "finish"],
                "source_binding": {"source_event": "source-beta", "race": "long"},
            },
            {
                "race_key": "edition-c", "race_family": "family-short", "year": 2032,
                "section": "Short", "type": "relay", "data_status": "available", "course_version": "course-b",
                "route_range": {"from": "mid", "to": "finish"}, "checkpoint_keys": ["mid", "finish"],
                "source_binding": {"source_event": "source-beta", "race": "short"},
            },
            {
                "race_key": "edition-planned", "race_family": "future-format", "year": 2033,
                "section": "Future", "type": "individual", "data_status": "planned", "course_version": "course-c",
                "route_range": {"from": "start", "to": "finish"}, "checkpoint_keys": ["start", "finish"],
            },
        ],
    }


class MultiyearRebuildTests(unittest.TestCase):
    def test_multiple_source_events_are_dispatched_once_in_one_run(self):
        config = synthetic_config()
        calls = []

        def import_eqtiming(group):
            calls.append((group["source_event_key"], sorted(group["bindings"])))
            return group["source_event_key"]

        outcomes = dispatch_source_groups(config, {"eqtiming": import_eqtiming})
        self.assertEqual(outcomes, ["source-alpha", "source-beta"])
        self.assertEqual(calls, [
            ("source-alpha", ["edition-a"]),
            ("source-beta", ["edition-b", "edition-c"]),
        ])

    def test_catalog_supports_repeated_family_arbitrary_families_and_planned_edition(self):
        config = synthetic_config()
        catalog = race_catalog(config)
        resolved = resolve_source_bindings(config)
        web = web_race_catalog(config, {"edition-a", "edition-b", "edition-c"})
        self.assertEqual([race["race_family"] for race in catalog].count("family-long"), 2)
        self.assertEqual({group["source_event_key"] for group in group_source_bindings(config)}, {"source-alpha", "source-beta"})
        self.assertNotIn("edition-planned", resolved)
        self.assertEqual(web["edition-planned"]["data_status"], "planned")
        self.assertFalse(web["edition-planned"]["source_available"])
        self.assertFalse(web["edition-planned"]["analyzable"])

    def test_malformed_and_unknown_provider_config_fails_clearly(self):
        malformed = synthetic_config()
        del malformed["races"][0]["source_binding"]
        with self.assertRaisesRegex(SourceBindingError, "has no source_binding"):
            resolve_source_bindings(malformed)

        unknown = synthetic_config()
        unknown["source_events"]["source-alpha"]["provider"] = "other"
        with self.assertRaisesRegex(SourceBindingError, "No importer registered for provider: other"):
            dispatch_source_groups(unknown, {"eqtiming": lambda group: group})

    def test_event_scoped_source_and_result_identities_can_coexist(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript((TOOLS / "schema.sql").read_text(encoding="utf-8"))
        for offset, event_key in enumerate(("source-alpha", "source-beta")):
            course_version = f"course-{offset}"
            connection.execute(
                """INSERT INTO course_versions(course_version,event_key,fingerprint,route_source,
                   route_asset,elevation_asset,raw_json) VALUES(?,?,?,?,?,?,?)""",
                (course_version, "portable-event", f"fingerprint-{offset}", "route.gpx", "route.json", "elevation.json", "{}"),
            )
            connection.execute(
                "INSERT INTO sources(code,provider,source_event_key,name,source_type) VALUES(?,?,?,?,?)",
                ("official_resultlist", "eqtiming", event_key, event_key, "csv"),
            )
            connection.execute(
                """INSERT INTO races(race_key,event_key,race_family,course_version,data_status,is_analyzable,
                   source_event_key,section_name,race_type,year) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (f"race-{event_key}", "portable-event", "family-long", course_version, "available", 1,
                 event_key, event_key, "individual", 2031 + offset),
            )
            source_id = connection.execute(
                "SELECT id FROM sources WHERE provider=? AND source_event_key=? AND code=?",
                ("eqtiming", event_key, "official_resultlist"),
            ).fetchone()[0]
            race_id = connection.execute("SELECT id FROM races WHERE race_key=?", (f"race-{event_key}",)).fetchone()[0]
            connection.execute(
                """INSERT INTO results(race_id,source_id,source_result_id,entity_type,name_as_published,
                   status,raw_json) VALUES(?,?,?,?,?,?,?)""",
                (race_id, source_id, "same-provider-id", "athlete", "Runner", "FINISHED", "{}"),
            )
            connection.execute(
                "INSERT INTO teams(source_external_id,team_name,normalized_name) VALUES(?,?,?)",
                (f"race-{event_key}:same-bib", "Team", "team"),
            )
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0], 2)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM results").fetchone()[0], 2)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM teams").fetchone()[0], 2)
        self.assertEqual(connection.execute("SELECT DISTINCT year FROM races").fetchall(), [(2031,), (2032,)])

    def test_canonical_output_names_are_year_neutral(self):
        from build_project_data import REPORT, REPORT_COMPAT, WEB_RESULTS, WEB_RESULTS_COMPAT

        self.assertEqual(WEB_RESULTS.name, "results.json")
        self.assertEqual(REPORT.name, "import-summary.json")
        self.assertEqual([path.name for path in WEB_RESULTS_COMPAT], ["results-2026.json"])
        self.assertEqual([path.name for path in REPORT_COMPAT], ["import-summary-2026.json"])
        self.assertEqual(WEB_RESULTS.read_bytes(), WEB_RESULTS_COMPAT[0].read_bytes())
        self.assertEqual(REPORT.read_bytes(), REPORT_COMPAT[0].read_bytes())
        for asset in (ROOT / "docs/assets/app.js", ROOT / "docs/assets/map-page.js"):
            source = asset.read_text(encoding="utf-8")
            self.assertIn("data/results.json", source)
            self.assertNotIn("data/results-2026.json", source)


if __name__ == "__main__":
    unittest.main()
