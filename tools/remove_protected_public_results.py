#!/usr/bin/env python3
"""Remove protected people and linked observations from Gotaleden browser data."""
from __future__ import annotations

import json
from pathlib import Path

from privacy import load_rules
from public_privacy_payload import withhold_protected_rows

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "config/privacy-suppressions.json"
TARGETS = [ROOT / "docs/data/results.json", ROOT / "docs/data/results-2026.json"]


def main() -> None:
    rules = load_rules(RULES, require_private=True)
    summary = {}
    for path in TARGETS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        summary[path.name] = withhold_protected_rows(payload, rules)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"status": "PASS", "removed_results": summary}))


if __name__ == "__main__":
    main()
