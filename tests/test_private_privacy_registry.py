import base64
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from privacy import load_rules, name_fingerprint, record_is_suppressed  # noqa: E402


class PrivatePrivacyRegistryTests(unittest.TestCase):
    def setUp(self):
        self.old = {key: os.environ.get(key) for key in (
            "LOPPANALYS_PRIVACY_REGISTRY_B64", "LOPPANALYS_PRIVACY_REGISTRY_PATH",
            "LOPPANALYS_REQUIRE_PRIVATE_REGISTRY",
        )}
        for key in self.old:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_public_policy_contains_no_subject_fingerprints(self):
        policy = json.loads((ROOT / "config/privacy-suppressions.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], 2)
        self.assertNotIn("suppressed_name_sha256", policy)
        self.assertNotRegex(json.dumps(policy), r"[0-9a-f]{64}")

    def test_publication_fails_closed_without_private_registry(self):
        with self.assertRaisesRegex(RuntimeError, "Private registry missing"):
            load_rules(ROOT / "config/privacy-suppressions.json", require_private=True)

    def test_private_registry_blocks_matching_row(self):
        registry = {"schema_version": 2, "entries": [{
            "subject_id": "case-test", "action": "remove_result", "scopes": ["*"],
            "require_review_for_new_matches": True,
            "approved_matches": [{"scope": "race-a", "identifiers": {"source_result_id": "123"}}],
            "match": {"normalized_name_sha256": name_fingerprint("Protected Person")},
        }]}
        os.environ["LOPPANALYS_PRIVACY_REGISTRY_B64"] = base64.b64encode(
            json.dumps(registry).encode("utf-8")
        ).decode("ascii")
        rules = load_rules(ROOT / "config/privacy-suppressions.json", require_private=True)
        self.assertTrue(record_is_suppressed({"name": "Protected Person", "source_result_id": "123"}, rules, scope="race-a"))
        with self.assertRaisesRegex(RuntimeError, "manual review"):
            record_is_suppressed({"name": "Protected Person", "source_result_id": "999"}, rules, scope="race-a")
        # Empty identifier approval must not authorize every same-name runner.
        rules["_entries"][0]["approved_matches"] = [{"scope": "race-a", "identifiers": {}}]
        with self.assertRaisesRegex(RuntimeError, "manual review"):
            record_is_suppressed({"name": "Protected Person", "source_result_id": "123"}, rules, scope="race-a")
        # Missing and blank fields must never satisfy an identity approval.
        rules["_entries"][0]["approved_matches"] = [{"scope": "race-a", "identifiers": {"source_result_id": ""}}]
        for row in ({"name": "Protected Person"}, {"name": "Protected Person", "source_result_id": ""}):
            with self.assertRaisesRegex(RuntimeError, "manual review"):
                record_is_suppressed(row, rules, scope="race-a")
        self.assertFalse(record_is_suppressed({"name": "Different Person"}, rules))


if __name__ == "__main__":
    unittest.main()
