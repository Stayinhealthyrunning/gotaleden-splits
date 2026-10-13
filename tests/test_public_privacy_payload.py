"""Synthetic regression tests for Gotaleden public individual and relay data."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from privacy import DISPLAY_NAME, name_fingerprint  # noqa: E402
from public_privacy_payload import public_relay_diagnostics, withhold_protected_rows  # noqa: E402


def registry(name="Protected Person", scopes=None):
    return {"_entries": [{
        "action": "remove_result",
        "match": {"normalized_name_sha256": name_fingerprint(name)},
        "scopes": scopes or ["*"],
    }], "display_name": DISPLAY_NAME}


def fixture():
    return {
        "races": {
            "solo": {"records": [
                {"name": "Protected Person", "bib": "17"},
                {"name": "Safe Runner", "bib": "18"},
            ]},
            "relay": {"records": [{"name": "Friendly Relay", "bib": "92"}]},
        },
        "splits": [
            {"race_key": "solo", "bib": "17", "elapsed_seconds": 10},
            {"race_key": "solo", "bib": "18", "elapsed_seconds": 11},
            {"race_key": "relay", "bib": "92", "elapsed_seconds": 12},
        ],
        "teams": [{
            "race_key": "relay", "bib": "92", "team_name": "Friendly Relay",
            "team_members": [{"name": "Protected Person"}, {"name": "Safe Runner"}],
        }],
        "team_members": [
            {"race_key": "relay", "team_bib": "92", "name": "Protected Person"},
            {"race_key": "relay", "team_bib": "92", "name": "Safe Runner"},
        ],
    }


class PublicPrivacyPayloadTests(unittest.TestCase):
    def test_solo_and_both_relay_member_representations(self):
        payload = fixture()
        summary = withhold_protected_rows(payload, registry())
        self.assertEqual(summary["removed_results"], 1)
        self.assertEqual(summary["removed_team_members"], 1)
        self.assertEqual(summary["removed_nested_team_members"], 1)
        self.assertEqual([r["bib"] for r in payload["races"]["solo"]["records"]], ["18"])
        self.assertEqual([r["bib"] for r in payload["splits"] if r["race_key"] == "solo"], ["18"])
        self.assertEqual([m["name"] for m in payload["teams"][0]["team_members"]], ["Safe Runner"])
        self.assertEqual([m["name"] for m in payload["team_members"]], ["Safe Runner"])

    def test_protected_team_name_removes_team_and_all_linked_rows(self):
        payload = fixture()
        summary = withhold_protected_rows(payload, registry("Friendly Relay"))
        self.assertEqual(summary["removed_teams"], 1)
        self.assertEqual(payload["teams"], [])
        self.assertEqual(payload["races"]["relay"]["records"], [])
        self.assertFalse([s for s in payload["splits"] if s["race_key"] == "relay"])
        self.assertFalse(payload["team_members"])
        self.assertEqual(len(payload["races"]["solo"]["records"]), 2)

    def test_scope_limits_suppression_to_relay(self):
        payload = fixture()
        withhold_protected_rows(payload, registry(scopes=["relay"]))
        self.assertEqual(len(payload["races"]["solo"]["records"]), 2)
        self.assertEqual(len(payload["teams"][0]["team_members"]), 1)

    def test_public_relay_reports_remove_individual_conflict_evidence(self):
        raw = {"races": {"relay": {"conflicts": 1}},
               "conflicts": [{"xml_value": "Protected Person",
                              "result_list_value": "Safe Runner", "team_bib": "92"}]}
        safe = public_relay_diagnostics(raw)
        self.assertEqual(safe["individual_conflict_details_withheld"], 1)
        self.assertEqual(safe["conflicts"], [])
        self.assertNotIn("Protected Person", str(safe))
        self.assertEqual(safe["races"]["relay"]["conflicts"], 1)

    def test_pseudonymous_record_and_nested_member_removed(self):
        payload = fixture()
        payload["races"]["solo"]["records"][0]["name"] = DISPLAY_NAME
        payload["teams"][0]["team_members"][0]["name"] = DISPLAY_NAME
        payload["team_members"][0]["name"] = DISPLAY_NAME
        withhold_protected_rows(payload, registry("Different Person"))
        self.assertEqual(len(payload["races"]["solo"]["records"]), 1)
        self.assertEqual(len(payload["teams"][0]["team_members"]), 1)
        self.assertEqual(len(payload["team_members"]), 1)


if __name__ == "__main__":
    unittest.main()
