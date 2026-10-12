#!/usr/bin/env python3
"""Remove protected people and linked observations from Gotaleden browser data."""
from __future__ import annotations

import json
from pathlib import Path

from privacy import DISPLAY_NAME, load_rules, normalize_name, record_is_suppressed

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "config/privacy-suppressions.json"
TARGETS = [ROOT / "docs/data/results.json", ROOT / "docs/data/results-2026.json"]


def main() -> None:
    rules = load_rules(RULES, require_private=True)
    summary = {}
    for path in TARGETS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        removed_refs = set()
        removed = 0
        for race_key, race in payload.get("races", {}).items():
            kept = []
            for row in race.get("records", []):
                blocked = normalize_name(row.get("name")) == normalize_name(DISPLAY_NAME)
                blocked = blocked or record_is_suppressed(row, rules, scope=race_key)
                if blocked:
                    for key in ("bib", "source_result_id", "public_contestant_uid"):
                        if row.get(key) not in (None, ""):
                            removed_refs.add((str(race_key), str(row[key])))
                    removed += 1
                else:
                    kept.append(row)
            race["records"] = kept
        payload["splits"] = [
            row for row in payload.get("splits", [])
            if (str(row.get("race_key") or ""), str(row.get("bib") or "")) not in removed_refs
        ]
        payload["team_members"] = [
            row for row in payload.get("team_members", [])
            if normalize_name(row.get("name")) != normalize_name(DISPLAY_NAME)
            and not record_is_suppressed(row, rules, scope=str(row.get("race_key") or "*"))
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        summary[path.name] = removed
    print(json.dumps({"status": "PASS", "removed_results": summary}))


if __name__ == "__main__":
    main()
