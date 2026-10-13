#!/usr/bin/env python3
"""Read-only privacy audit for source SQLite files tracked in *public* Git.

Never log names, fingerprints, record IDs, raw JSON, or private registry entries.
This is a risk detector, not a complete GDPR compliance certification.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from privacy import load_rules, name_fingerprint

ROOT = Path(__file__).resolve().parents[1]
NAME_FIELDS = {
    "name", "canonical_name", "normalized_name", "name_as_published",
    "member_name_as_published", "runner_name_as_published", "published_name",
    "first_name", "last_name", "firstname", "lastname", "surname",
    "team_name", "listed_contact_name", "navnformatert", "fornavn", "etternavn",
}
GIVEN_FIELDS = {"first_name", "firstname", "fornavn"}
FAMILY_FIELDS = {"last_name", "lastname", "surname", "etternavn"}
JSON_FIELDS = {"raw_json", "source_evidence", "source_payload", "metadata_json", "person_json"}


def _candidate_names(record: dict) -> set[str]:
    names: set[str] = set()

    def visit(obj, depth=0):
        if depth > 7:
            return
        if isinstance(obj, list):
            for item in obj:
                visit(item, depth + 1)
        elif isinstance(obj, dict):
            parts = {str(k).casefold(): v for k, v in obj.items()}
            for key, value in parts.items():
                if key in NAME_FIELDS and isinstance(value, str) and value.strip():
                    names.add(value.strip())
                if key in JSON_FIELDS and isinstance(value, str) and value.startswith(("{", "[")):
                    try:
                        visit(json.loads(value), depth + 1)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(value, (list, dict)):
                    visit(value, depth + 1)
            for first_key in GIVEN_FIELDS:
                for last_key in FAMILY_FIELDS:
                    first, last = parts.get(first_key), parts.get(last_key)
                    if isinstance(first, str) and isinstance(last, str) and first.strip() and last.strip():
                        names.add(first.strip() + " " + last.strip())
                        names.add(last.strip() + " " + first.strip())

    visit(record)
    # Some sources store "Last, First", while the protected registry stores "First Last".
    for name in list(names):
        if "," in name:
            bits = [x.strip() for x in name.split(",", 1)]
            if all(bits):
                names.add(bits[1] + " " + bits[0])
    return names


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def scan_sqlite(path: Path, protected_fingerprints: set[str]) -> tuple[int, int, int]:
    """Return (name-bearing rows, protected-name matches, explicit minors).

    Counts are private to the caller. Never include a subject identity in a log.
    """
    rows_seen = protected_matches = minors = 0
    with contextlib.ExitStack() as stack:
        source = path
        if path.name.endswith(".sqlite.gz"):
            tmpdir = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            source = tmpdir / "source.sqlite"
            with gzip.open(path, "rb") as inp, source.open("wb") as out:
                shutil.copyfileobj(inp, out)
        uri = source.resolve().as_uri() + "?mode=ro"
        conn = stack.enter_context(sqlite3.connect(uri, uri=True))
        conn.execute("PRAGMA query_only=ON")
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        for table in tables:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({_quoted(table)})")]
            selected = [c for c in columns if c.casefold() in NAME_FIELDS | JSON_FIELDS]
            if not selected:
                continue
            extra = [c for c in columns if c.casefold() == "age"]
            selected += [c for c in extra if c not in selected]
            query = "SELECT " + ",".join(_quoted(c) for c in selected) + " FROM " + _quoted(table)
            for record in conn.execute(query):
                row = dict(zip(selected, record))
                names = _candidate_names(row)
                if not names:
                    continue
                rows_seen += 1
                if protected_fingerprints and any(
                    name_fingerprint(name) in protected_fingerprints for name in names
                ):
                    protected_matches += 1
                age = row.get("age")
                if isinstance(age, int) and not isinstance(age, bool) and 0 <= age < 18:
                    minors += 1
    return rows_seen, protected_matches, minors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()
    # Do not relax this: absent/malformed secret must fail the audit.
    rules = load_rules(ROOT / "config/privacy-suppressions.json", require_private=True)
    fingerprints = {
        entry["match"]["normalized_name_sha256"] for entry in rules["_entries"]
    }
    risky = False
    for source in args.sources:
        if not source.is_file():
            raise SystemExit("Source audit blocked: required tracked source file not found")
        count, hits, minors = scan_sqlite(source, fingerprints)
        if not count:
            raise SystemExit("Source audit blocked: database had no inspectable named records")
        # The public build log must not include person-level evidence or exact records.
        print(f"Source archive examined: {source.suffix}; identity matches={'present' if hits else 'none'}; explicit minor ages={'present' if minors else 'none'}")
        risky |= bool(hits or minors)
    if risky:
        print("PRIVACY REVIEW REQUIRED: public source archive may contain protected identities or identifiable minors")
        return 1
    print("LIMITED CHECK PASS: no exact protected-name fingerprints or explicit minor ages observed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
