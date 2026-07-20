#!/usr/bin/env python3
"""Parsers and evidence rules for the official EQ Timing event 77906 files."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "source" / "eqtiming"

PRIMARY_RESULTS = "Resultlist-77906-20260719155435.csv"
PRIMARY_RELAY_LEGS = "Startlist-77906-20260719155427.xml"

RESULTLIST_FILES = (
    "Resultlist-77906-20260719155309.csv",
    "Resultlist-77906-20260719155433.csv",
    "Resultlist-77906-20260719155434.csv",
    PRIMARY_RESULTS,
)
STARTLIST_FILES = (
    PRIMARY_RELAY_LEGS,
    "Startlist-77906-20260719155429.csv",
    "Startlist-77906-20260719155430.csv",
)

RACE_RULES = {
    "individual-75-2026": {"name": "Ultra 75 km", "start_time": "07:00:00"},
    "individual-35-2026": {"name": "Sprint 35 km", "start_time": "12:00:00"},
    "relay-75-2026": {"name": "Stafett 75 km", "start_time": "08:00:00", "legs": 9},
    "relay-35-2026": {"name": "Stafett 35 km", "start_time": "12:00:00", "legs": 4},
}


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_hms(value: str | None) -> float | None:
    value = clean(value)
    if not value or value.upper() in {"DNF", "DNS", "DSQ"}:
        return None
    parts = value.split(":")
    if len(parts) == 2:
        hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
    else:
        return None
    return hours * 3600 + minutes * 60 + seconds


def to_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def read_csv_file(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str | None]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows = list(reader)
    if not rows:
        return [], []
    width = max(len(row) for row in rows)
    header = list(rows[0])
    while len(header) < width:
        header.append(f"_unlabelled_{len(header) + 1}")
    normalized_header: list[str] = []
    seen: Counter[str] = Counter()
    for index, field in enumerate(header, 1):
        field = field or f"_unlabelled_{index}"
        seen[field] += 1
        normalized_header.append(field if seen[field] == 1 else f"{field}_{seen[field]}")
    records: list[dict[str, str | None]] = []
    for row in rows[1:]:
        padded = row + [""] * (width - len(row))
        records.append({key: (value if value != "" else None) for key, value in zip(normalized_header, padded)})
    return normalized_header, records


def load_primary_results() -> list[dict[str, str | None]]:
    _, rows = read_csv_file(SOURCE_DIR / PRIMARY_RESULTS, ";")
    return rows


def load_xml_starts() -> list[dict[str, str]]:
    root = ET.parse(SOURCE_DIR / PRIMARY_RELAY_LEGS).getroot()
    return [dict(node.attrib) for node in root.findall("start")]


def member_positions(value: str | None) -> list[str | None]:
    """Preserve empty positions: they carry relay-leg meaning."""
    if not value:
        return []
    text = value.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return [clean(part) for part in text.split(",")]


def xml_runner_name(entry: dict[str, str] | None) -> str | None:
    if not entry:
        return None
    return clean(" ".join(part for part in (clean(entry.get("fornavn")), clean(entry.get("etternavn"))) if part))


def leg_start_number(race_key: str, team_bib: int, leg_no: int) -> int:
    if race_key == "relay-75-2026":
        return leg_no * 1000 + team_bib
    if race_key == "relay-35-2026":
        return team_bib + leg_no * 1000
    raise ValueError(f"Not a relay race: {race_key}")


def build_relay_assignments(
    race_key: str,
    team_rows: list[dict[str, str | None]],
    xml_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rule = RACE_RULES[race_key]
    max_legs = int(rule["legs"])
    start_time = str(rule["start_time"])
    xml_index: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in xml_rows:
        number = to_int(row.get("startno"))
        if number is not None:
            xml_index.setdefault((row.get("starttid", ""), number), []).append(row)

    assignments: list[dict[str, Any]] = []
    comparisons = matches = 0
    duplicate_codes: list[int] = []
    team_bibs = {int(row["Startnumber"] or 0) for row in team_rows}

    for team in team_rows:
        bib = int(team["Startnumber"] or 0)
        result_members = member_positions(team.get("Surname"))
        for leg_no in range(1, max_legs + 1):
            code = leg_start_number(race_key, bib, leg_no)
            candidates = xml_index.get((start_time, code), [])
            if len(candidates) > 1:
                duplicate_codes.append(code)
            xml_entry = candidates[0] if len(candidates) == 1 else None
            xml_name = xml_runner_name(xml_entry)
            result_name = result_members[leg_no - 1] if leg_no <= len(result_members) else None
            if xml_name and result_name:
                comparisons += 1
                if normalize_name(xml_name) == normalize_name(result_name):
                    matches += 1
                    status = "verified_xml_and_result_list"
                    evidence = f"{PRIMARY_RELAY_LEGS} startno={code} + ordered result member list"
                else:
                    status = "conflict"
                    evidence = f"Conflict: XML runner {xml_name}; result list runner {result_name}"
            elif xml_name:
                status = "verified_xml"
                evidence = f"{PRIMARY_RELAY_LEGS} startno={code}"
            else:
                status = "missing"
                evidence = (
                    f"{PRIMARY_RELAY_LEGS} startno={code} has no runner name"
                    if xml_entry
                    else f"No {PRIMARY_RELAY_LEGS} entry for startno={code} at {start_time}"
                )
            assignments.append(
                {
                    "race_key": race_key,
                    "team_bib": str(bib),
                    "team_name": clean(team.get("Firstname")),
                    "leg_no": leg_no,
                    "source_start_number": str(code),
                    "xml_runner": xml_name,
                    "result_list_runner": result_name,
                    "runner_name": xml_name if status.startswith("verified_") else None,
                    "assignment_status": status,
                    "source_evidence": evidence,
                    "raw_xml": xml_entry,
                }
            )

    relevant_codes = {leg_start_number(race_key, bib, leg) for bib in team_bibs for leg in range(1, max_legs + 1)}
    cross_race_code_collisions = sorted(
        int(row["startno"])
        for row in xml_rows
        if to_int(row.get("startno")) in relevant_codes and row.get("starttid") != start_time
    )
    pattern = {
        "formula": (
            "startno = leg_no * 1000 + team_bib"
            if race_key == "relay-75-2026"
            else "startno = team_bib + leg_no * 1000 (prefix 2-5 maps to legs 1-4)"
        ),
        "required_start_time": start_time,
        "team_count": len(team_rows),
        "possible_leg_slots": len(team_rows) * max_legs,
        "xml_and_result_list_comparisons": comparisons,
        "matching_comparisons": matches,
        "conflicting_comparisons": comparisons - matches,
        "duplicate_expected_codes": duplicate_codes,
        "same_numeric_codes_in_other_start_times_count": len(cross_race_code_collisions),
        "same_numeric_codes_in_other_start_times_sample": cross_race_code_collisions[:20],
        "start_time_is_part_of_identity": True,
        "verified": not duplicate_codes and comparisons > 0,
    }
    return assignments, pattern


def relay_member_sources(
    team: dict[str, str | None], assignments: list[dict[str, Any]], max_legs: int
) -> list[dict[str, Any]]:
    evidence_by_name: dict[str, dict[str, Any]] = {}
    positions = member_positions(team.get("Surname"))
    for leg_no, name in enumerate(positions[:max_legs], 1):
        if name:
            key = normalize_name(name)
            item = evidence_by_name.setdefault(key, {"name": name, "evidence": [], "legs": []})
            item["evidence"].append(f"{PRIMARY_RESULTS} ordered member list position {leg_no}")
    for assignment in assignments:
        name = assignment.get("xml_runner")
        if name:
            key = normalize_name(name)
            item = evidence_by_name.setdefault(key, {"name": name, "evidence": [], "legs": []})
            item["evidence"].append(
                f"{PRIMARY_RELAY_LEGS} startno={assignment['source_start_number']}"
            )
            item["legs"].append(assignment["leg_no"])
    return [
        {
            "name": item["name"],
            "normalized_name": key,
            "source_evidence": " | ".join(dict.fromkeys(item["evidence"])),
            "legs_in_xml": sorted(set(item["legs"])),
        }
        for key, item in sorted(evidence_by_name.items())
    ]


def _races_for_file(name: str, rows: list[dict[str, Any]] | None, text: str) -> list[str]:
    race_names = [str(rule["name"]) for rule in RACE_RULES.values()]
    found: set[str] = set()
    for race_name in race_names:
        if race_name in text:
            found.add(race_name)
    if rows:
        for row in rows:
            for field in ("Stage", "Race", "RaceName", "Group", "GroupdName"):
                if row.get(field) in race_names:
                    found.add(str(row[field]))
    if name == PRIMARY_RELAY_LEGS:
        found.update(race_names)
    if name == "Startlist-77906-20260719155430.csv":
        found.update(race_names)
    if name == "Startlist-77906-20260719155429.csv":
        found.update(race_names)
    return sorted(found)


def analyze_source_files() -> dict[str, Any]:
    structured: dict[str, set[str]] = {}
    analyses: list[dict[str, Any]] = []
    for path in sorted(SOURCE_DIR.iterdir()):
        if not path.is_file():
            continue
        data = path.read_bytes()
        encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
        text = data.decode("utf-8-sig")
        rows: list[dict[str, Any]] | None = None
        fields: list[str] = []
        delimiter = None
        fmt = path.suffix.lower().lstrip(".")
        if path.suffix.lower() == ".xml":
            root = ET.fromstring(text)
            rows = [dict(node.attrib) for node in root.findall("start")]
            fields = sorted({key for row in rows for key in row})
        elif path.suffix.lower() == ".csv":
            first_line = text.splitlines()[0] if text.splitlines() else ""
            delimiter = "tab" if "\t" in first_line else ("semicolon" if ";" in first_line else "comma")
            char = {"tab": "\t", "semicolon": ";", "comma": ","}[delimiter]
            fields, rows = read_csv_file(path, char)
        structured[path.name] = set(fields)
        races = _races_for_file(path.name, rows, text)
        is_result = path.name.startswith("Resultlist") or path.name.startswith(("individual-", "relay-"))
        is_start = path.name.startswith("Startlist")
        relay_result = any(name.startswith("Stafett") for name in races) and is_result
        individual_result = any(name in {"Ultra 75 km", "Sprint 35 km"} for name in races) and is_result
        contains_members = (
            path.name == PRIMARY_RELAY_LEGS
            or (relay_result and rows is not None and any(clean(row.get("Surname")) and str(row.get("Surname")).startswith("(") for row in rows))
        )
        analyses.append(
            {
                "file_name": path.name,
                "format": fmt,
                "delimiter": delimiter,
                "encoding": encoding,
                "byte_size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "line_count": len(text.splitlines()),
                "record_count": len(rows) if rows is not None else None,
                "field_count": len(fields) if fields else None,
                "fields": fields,
                "races": races,
                "contains_individual_results": individual_result,
                "contains_relay_results": relay_result,
                "contains_start_list": is_start,
                "contains_relay_members": contains_members,
                "contains_team_name": relay_result,
                "contains_leg_encoding": path.name == PRIMARY_RELAY_LEGS,
                "contains_intermediate_splits": bool(rows and any(clean(row.get("PointName")) not in {None, "Mål"} for row in rows)),
                "finish_results_only": is_result,
            }
        )

    for analysis in analyses:
        fields = structured[analysis["file_name"]]
        other_fields: set[str] = set()
        for other_name, other in structured.items():
            if other_name != analysis["file_name"]:
                other_fields.update(other)
        analysis["fields_unique_to_file"] = sorted(fields - other_fields)
        same_hash = [
            other["file_name"]
            for other in analyses
            if other["file_name"] != analysis["file_name"] and other["sha256"] == analysis["sha256"]
        ]
        analysis["byte_identical_to"] = same_hash

    return {
        "event_id": 77906,
        "primary_result_source": PRIMARY_RESULTS,
        "primary_relay_leg_source": PRIMARY_RELAY_LEGS,
        "files": analyses,
        "source_priority": [
            PRIMARY_RESULTS,
            PRIMARY_RELAY_LEGS,
            "Other official Resultlist files (cross-validation)",
            "Startlist-77906-20260719155430.csv (start-data cross-validation)",
            "Legacy 81-column per-race CSV files (fallback and raw-field preservation)",
        ],
        "notes": [
            "Startlist-77906-20260719155429.csv has eight labelled header fields but nine values in data rows; the ninth field is retained as _unlabelled_9.",
            "Empty member-list positions are semantically significant and are preserved.",
            "No official file contains separate checkpoint passages; no intermediate split is synthesized.",
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
