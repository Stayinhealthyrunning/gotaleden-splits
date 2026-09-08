import ast
import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from eqtiming_official_import import (  # noqa: E402
    bind_primary_results,
    eqtiming_source_context,
    load_primary_results,
)
from source_bindings import SourceBindingError, resolve_source_bindings  # noqa: E402


class SourceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/races.json").read_text(encoding="utf-8"))
        cls.source_event, cls.bindings = eqtiming_source_context(cls.config)

    def test_four_editions_share_one_source_event(self):
        self.assertEqual(len(self.bindings), 4)
        self.assertEqual({item["source_event_key"] for item in self.bindings.values()}, {"eqtiming-gotaleden-2026"})
        self.assertTrue(all(item["source_event"] is self.source_event for item in self.bindings.values()))

    def test_source_race_mapping_and_expected_counts_come_from_config(self):
        rows = load_primary_results(self.source_event)
        grouped = bind_primary_results(rows, self.source_event, self.bindings)
        for race_key, resolved in self.bindings.items():
            binding = resolved["source_race"]
            self.assertEqual(len(grouped[race_key]), binding["expected_records"])
            self.assertEqual({row["Stage"] for row in grouped[race_key]}, {binding["source_race_name"]})
        self.assertEqual(sum(map(len, grouped.values())), self.source_event["expected_records"])

    def test_relay_rules_are_bound_to_configured_editions(self):
        for race_key, resolved in self.bindings.items():
            relay = resolved["source_race"]["relay"]
            if resolved["race"]["type"] == "relay":
                self.assertIsInstance(relay, dict, race_key)
                self.assertGreater(relay["legs"], 1)
                self.assertIn("start_number", relay)
            else:
                self.assertIsNone(relay, race_key)

    def test_invalid_source_config_fails_clearly(self):
        unknown = copy.deepcopy(self.config)
        unknown["races"][0]["source_binding"]["source_event"] = "missing"
        with self.assertRaisesRegex(SourceBindingError, "unknown source event"):
            resolve_source_bindings(unknown)

        wrong_total = copy.deepcopy(self.config)
        wrong_total["source_events"]["eqtiming-gotaleden-2026"]["expected_records"] += 1
        with self.assertRaisesRegex(SourceBindingError, "does not match binding total"):
            eqtiming_source_context(wrong_total)

        wrong_stage = copy.deepcopy(self.config)
        wrong_stage["source_events"]["eqtiming-gotaleden-2026"]["race_bindings"]["ultra"]["source_race_name"] = "Unknown stage"
        source_event, bindings = eqtiming_source_context(wrong_stage)
        with self.assertRaisesRegex(SourceBindingError, "has 0, expected"):
            bind_primary_results(load_primary_results(source_event), source_event, bindings)

    def test_routing_has_no_current_event_or_edition_special_cases(self):
        files_and_functions = {
            "tools/source_bindings.py": {"resolve_source_bindings"},
            "tools/eqtiming_official_import.py": {
                "eqtiming_source_context", "bind_primary_results", "leg_start_number",
                "build_relay_assignments", "analyze_source_files",
            },
            "tools/build_official_data.py": {
                "_load_public_contestants", "_cross_validation_indexes", "_insert_relay_data",
                "import_all_official",
            },
        }
        forbidden = (
            "77906", "607", "individual-75-2026", "individual-35-2026",
            "relay-75-2026", "relay-35-2026", "EXPECTED_COUNTS", "RACE_RULES", "SOURCE_POINT_KEYS",
        )
        for relative, function_names in files_and_functions.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            tree = ast.parse(source)
            routing = "\n".join(
                ast.get_source_segment(source, node) or ""
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in function_names
            )
            self.assertEqual({node.name for node in tree.body if isinstance(node, ast.FunctionDef)} & function_names, function_names)
            for token in forbidden:
                self.assertNotIn(token, routing, f"{relative}: {token}")


if __name__ == "__main__":
    unittest.main()
