#!/usr/bin/env python3
"""EQ Timing adapter: configured source files, validation, and evidence rules."""
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

from source_bindings import SourceBindingError, group_source_bindings

ROOT = Path(__file__).resolve().parents[1]


def _validate_eqtiming_context(
    source_event_key: str, source_event: dict[str, Any], resolved: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    required_event = (
        "event_id", "results_url", "contestant_endpoint", "contestants_endpoint", "source_dir",
        "public_snapshot", "primary_results", "result_files", "result_list_files", "expected_records", "checkpoint_map",
    )
    missing_event = [key for key in required_event if source_event.get(key) in (None, "", [], {})]
    if source_event.get("provider") != "eqtiming" or missing_event:
        raise SourceBindingError(f"Invalid EQ Timing source event {source_event_key!r}; missing or invalid: {', '.join(missing_event) or 'provider'}")
    identity = source_event.get("person_identity")
    if not isinstance(identity, dict) or identity.get("scope") not in {"race_edition", "source_event", "provider"}:
        raise SourceBindingError(f"EQ Timing source event {source_event_key!r} must declare a valid person_identity scope")
    if identity.get("id_type") in (None, "") or identity.get("confidence") != "verified":
        raise SourceBindingError(f"EQ Timing source event {source_event_key!r} has incomplete person_identity evidence")
    required_race = ("source_race_name", "legacy_csv", "expected_records", "start_time")
    has_relay = False
    for race_key, item in resolved.items():
        binding = item["source_race"]
        missing_race = [key for key in required_race if binding.get(key) in (None, "")]
        relay = binding.get("relay")
        if missing_race:
            raise SourceBindingError(f"Invalid source binding for {race_key}; missing: {', '.join(missing_race)}")
        if (item["race"].get("type") == "relay") != isinstance(relay, dict):
            raise SourceBindingError(f"Source relay rule does not match race type for {race_key}")
        if isinstance(relay, dict):
            has_relay = True
            start_number = relay.get("start_number")
            if not relay.get("legs") or not isinstance(start_number, dict):
                raise SourceBindingError(f"Invalid relay source rule for {race_key}")
            for key in ("team_bib_multiplier", "leg_multiplier", "offset", "description"):
                if key not in start_number:
                    raise SourceBindingError(f"Relay source rule for {race_key} is missing {key}")
    if has_relay:
        relay_event_fields = ("primary_relay_legs", "start_list_files", "start_cross_validation_file")
        missing_relay = [key for key in relay_event_fields if source_event.get(key) in (None, "", [])]
        if missing_relay:
            raise SourceBindingError(f"EQ Timing source event {source_event_key!r} is missing relay fields: {', '.join(missing_relay)}")
    expected_total = sum(int(item["source_race"]["expected_records"]) for item in resolved.values())
    if expected_total != int(source_event["expected_records"]):
        raise SourceBindingError(
            f"Source event expected_records={source_event['expected_records']} does not match binding total {expected_total}"
        )
    return source_event, resolved


def eqtiming_source_contexts(config: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, dict[str, Any]]]]:
    return [
        (group["source_event_key"], *_validate_eqtiming_context(
            group["source_event_key"], group["source_event"], group["bindings"]
        ))
        for group in group_source_bindings(config)
        if group["provider"] == "eqtiming"
    ]


def eqtiming_source_context(
    config: dict[str, Any], source_event_key: str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    contexts = {key: (event, bindings) for key, event, bindings in eqtiming_source_contexts(config)}
    if source_event_key is not None:
        if source_event_key not in contexts:
            raise SourceBindingError(f"Unknown EQ Timing source event {source_event_key!r}")
        return contexts[source_event_key]
    if len(contexts) != 1:
        raise SourceBindingError("Select one EQ Timing source event explicitly")
    return next(iter(contexts.values()))


def source_dir(source_event: dict[str, Any]) -> Path:
    return ROOT / str(source_event["source_dir"])


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


def person_identity_evidence(contestant: dict[str, Any], source_event: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate EQ Timing contestant fields into provider-neutral identity evidence."""
    identity = source_event.get("person_identity") or {}
    external_id = to_int(contestant.get("UID"))
    if external_id is None:
        return []
    return [{
        "provider": source_event["provider"], "id_type": identity["id_type"],
        "scope": identity["scope"], "external_id": external_id,
        "confidence": identity["confidence"], "evidence": identity.get("evidence"),
    }]


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


def load_primary_results(source_event: dict[str, Any]) -> list[dict[str, str | None]]:
    _, rows = read_csv_file(source_dir(source_event) / source_event["primary_results"], ";")
    return rows


def bind_primary_results(
    rows: list[dict[str, str | None]], source_event: dict[str, Any],
    bindings: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, str | None]]]:
    primary_results = source_event["primary_results"]
    expected_total = int(source_event["expected_records"])
    if len(rows) != expected_total:
        raise SourceBindingError(f"{primary_results} has {len(rows)} rows, expected {expected_total}")
    grouped: dict[str, list[dict[str, str | None]]] = {}
    for race_key, resolved in bindings.items():
        binding = resolved["source_race"]
        matches = [row for row in rows if row.get("Stage") == binding["source_race_name"]]
        expected = int(binding["expected_records"])
        if len(matches) != expected:
            raise SourceBindingError(f"{primary_results}: {race_key} has {len(matches)}, expected {expected}")
        grouped[race_key] = matches
    if sum(map(len, grouped.values())) != expected_total:
        raise SourceBindingError(f"{primary_results} source race mapping is overlapping or incomplete")
    return grouped


def load_xml_starts(source_event: dict[str, Any]) -> list[dict[str, str]]:
    root = ET.parse(source_dir(source_event) / source_event["primary_relay_legs"]).getroot()
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


def leg_start_number(binding: dict[str, Any], team_bib: int, leg_no: int) -> int:
    rule = binding["relay"]["start_number"]
    return int(team_bib * int(rule["team_bib_multiplier"]) + leg_no * int(rule["leg_multiplier"]) + int(rule["offset"]))


def build_relay_assignments(
    race_key: str,
    team_rows: list[dict[str, str | None]],
    xml_rows: list[dict[str, str]],
    binding: dict[str, Any],
    source_event: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    relay_rule = binding["relay"]
    max_legs = int(relay_rule["legs"])
    start_time = str(binding["start_time"])
    relay_file = str(source_event["primary_relay_legs"])
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
            code = leg_start_number(binding, bib, leg_no)
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
                    evidence = f"{relay_file} startno={code} + ordered result member list"
                else:
                    status = "conflict"
                    evidence = f"Conflict: XML runner {xml_name}; result list runner {result_name}"
            elif xml_name:
                status = "verified_xml"
                evidence = f"{relay_file} startno={code}"
            else:
                status = "missing"
                evidence = (
                    f"{relay_file} startno={code} has no runner name"
                    if xml_entry
                    else f"No {relay_file} entry for startno={code} at {start_time}"
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

    relevant_codes = {leg_start_number(binding, bib, leg) for bib in team_bibs for leg in range(1, max_legs + 1)}
    cross_race_code_collisions = sorted(
        int(row["startno"])
        for row in xml_rows
        if to_int(row.get("startno")) in relevant_codes and row.get("starttid") != start_time
    )
    pattern = {
        "formula": relay_rule["start_number"]["description"],
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
    team: dict[str, str | None], assignments: list[dict[str, Any]], max_legs: int,
    source_event: dict[str, Any],
) -> list[dict[str, Any]]:
    primary_results = str(source_event["primary_results"])
    primary_relay_legs = str(source_event.get("primary_relay_legs") or "")
    evidence_by_name: dict[str, dict[str, Any]] = {}
    positions = member_positions(team.get("Surname"))
    for leg_no, name in enumerate(positions[:max_legs], 1):
        if name:
            key = normalize_name(name)
            item = evidence_by_name.setdefault(key, {"name": name, "evidence": [], "legs": []})
            item["evidence"].append(f"{primary_results} ordered member list position {leg_no}")
    for assignment in assignments:
        name = assignment.get("xml_runner")
        if name:
            key = normalize_name(name)
            item = evidence_by_name.setdefault(key, {"name": name, "evidence": [], "legs": []})
            item["evidence"].append(
                f"{primary_relay_legs} startno={assignment['source_start_number']}"
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


def _races_for_file(
    name: str, rows: list[dict[str, Any]] | None, text: str,
    source_event: dict[str, Any], bindings: dict[str, dict[str, Any]],
) -> list[str]:
    race_names = [str(item["source_race"]["source_race_name"]) for item in bindings.values()]
    found: set[str] = set()
    for race_name in race_names:
        if race_name in text:
            found.add(race_name)
    if rows:
        for row in rows:
            for field in ("Stage", "Race", "RaceName", "Group", "GroupdName"):
                if row.get(field) in race_names:
                    found.add(str(row[field]))
    if name in source_event.get("all_races_files", []):
        found.update(race_names)
    return sorted(found)


def analyze_source_files(source_event: dict[str, Any], bindings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    directory = source_dir(source_event)
    primary_results = str(source_event["primary_results"])
    primary_relay_legs = str(source_event["primary_relay_legs"])
    relay_names = {
        str(item["source_race"]["source_race_name"])
        for item in bindings.values() if isinstance(item["source_race"].get("relay"), dict)
    }
    individual_names = {
        str(item["source_race"]["source_race_name"])
        for item in bindings.values() if item["source_race"].get("relay") is None
    }
    result_files = set(source_event["result_files"])
    result_files.update(Path(item["source_race"]["legacy_csv"]).name for item in bindings.values())
    start_files = set(source_event.get("start_list_files", []))
    structured: dict[str, set[str]] = {}
    analyses: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
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
        races = _races_for_file(path.name, rows, text, source_event, bindings)
        is_result = path.name in result_files
        is_start = path.name in start_files
        relay_result = any(name in relay_names for name in races) and is_result
        individual_result = any(name in individual_names for name in races) and is_result
        contains_members = (
            bool(primary_relay_legs) and path.name == primary_relay_legs
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
                "contains_leg_encoding": bool(primary_relay_legs) and path.name == primary_relay_legs,
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
        "event_id": source_event["event_id"],
        "primary_result_source": primary_results,
        "primary_relay_leg_source": primary_relay_legs,
        "files": analyses,
        "source_priority": [item for item in (
            primary_results,
            primary_relay_legs or None,
            "Other official Resultlist files (cross-validation)",
            f"{source_event['start_cross_validation_file']} (start-data cross-validation)" if source_event.get("start_cross_validation_file") else None,
            "Legacy 81-column per-race CSV files (fallback and raw-field preservation)",
        ) if item],
        "notes": list(source_event.get("notes", [])),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
