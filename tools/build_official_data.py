#!/usr/bin/env python3
"""Build SQLite, web JSON, and reports from the official EQ Timing files."""
from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from build_project_data import (
    CONFIG,
    DB,
    REPORT,
    ROOT,
    WEB_RESULTS,
    WEB_ROUTE,
    clean,
    load_route,
    normalize,
    prepare_db,
    status_code,
    to_float,
    to_int,
)
from eqtiming_official_import import (
    PRIMARY_RELAY_LEGS,
    PRIMARY_RESULTS,
    RACE_RULES,
    RESULTLIST_FILES,
    SOURCE_DIR,
    analyze_source_files,
    build_relay_assignments,
    clean as official_clean,
    load_primary_results,
    load_xml_starts,
    normalize_name,
    parse_hms,
    read_csv_file,
    relay_member_sources,
    write_json,
)

EXPECTED_COUNTS = {
    "individual-75-2026": 274,
    "individual-35-2026": 163,
    "relay-75-2026": 121,
    "relay-35-2026": 49,
}
PUBLIC_API_SNAPSHOT = ROOT / "data" / "source" / "eqtiming" / "api" / "event-77906-contestants.json"
SOURCE_POINT_KEYS = {
    "Skatås": "skatas",
    "Kåsjön": "kasjon",
    "Jonsered": "jonsered",
    "Lerum": "lerum",
    "Floda": "floda",
    "Tollered": "tollered",
    "Norsesund": "norsesund",
    "V:a Bodarna": "vastra_bodarna",
    "Nolhaga": "nolhaga",
    "Mål": "alingsas",
}


def _load_public_contestants() -> dict[str, dict[str, Any]]:
    payload = json.loads(PUBLIC_API_SNAPSHOT.read_text(encoding="utf-8"))
    contestants = payload.get("contestants", {})
    if payload.get("event_id") != 77906 or payload.get("response_count") != 607 or not payload.get("passes_included"):
        raise ValueError(f"Incomplete public EQ Timing snapshot: {PUBLIC_API_SNAPSHOT}")
    return {str(key): value for key, value in contestants.items()}


def _public_passes(contestant: dict[str, Any]) -> list[dict[str, Any]]:
    legs = contestant.get("EtappeDeltaker") or {}
    passages: list[dict[str, Any]] = []
    for leg in legs.values():
        passages.extend((leg.get("Passeringer") or {}).values())
    return sorted(passages, key=lambda item: int((item.get("StasjonsOppsett") or {}).get("Sortering") or 0))


def _legacy_rows(race: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    with (ROOT / race["source_csv"]).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _cross_validation_indexes() -> tuple[dict[str, dict[tuple[str, str], dict[str, Any]]], dict[tuple[str, str], dict[str, Any]]]:
    result_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for file_name in RESULTLIST_FILES:
        if file_name == PRIMARY_RESULTS:
            continue
        _, rows = read_csv_file(SOURCE_DIR / file_name, ";")
        result_indexes[file_name] = {
            (str(row.get("Race") or ""), str(row.get("Startnumber") or "")): row for row in rows
        }
    _, start_rows = read_csv_file(SOURCE_DIR / "Startlist-77906-20260719155430.csv", "\t")
    start_index = {(str(row.get("Start Time") or ""), str(row.get("BIB") or "")): row for row in start_rows}
    return result_indexes, start_index


def _insert_catalog(conn: sqlite3.Connection, config: dict[str, Any], route: dict[str, Any]) -> dict[str, tuple[int, int, float]]:
    with conn:
        conn.executemany(
            "INSERT INTO sources(code,name,base_url,source_type) VALUES(?,?,?,?)",
            [
                ("eqtiming_official_resultlist", PRIMARY_RESULTS, "https://live.eqtiming.com/77906", "csv"),
                ("eqtiming_startlist_xml", PRIMARY_RELAY_LEGS, "https://live.eqtiming.com/77906", "xml"),
                ("eqtiming_legacy_csv", "EQ Timing 81-column finish exports", "https://live.eqtiming.com/77906", "csv"),
                ("eqtiming_public_api", "EQ Timing public contestant snapshot", "https://live.eqtiming.com/api/Contestants/77906?passes=true", "json"),
            ],
        )
    checkpoints = {checkpoint["key"]: checkpoint for checkpoint in config["checkpoints"]}
    catalog: dict[str, tuple[int, int, float]] = {}
    for race in config["races"]:
        gpx_distance = route["full_distance_km"] if race["route_start"] == "gothenburg" else route["floda_start"]["remaining_distance_km"]
        with conn:
            conn.execute(
                """INSERT INTO races(race_key,section_name,source_race_name,race_type,year,race_date,
                   nominal_distance_km,gpx_distance_km,official_url) VALUES(?,?,?,?,?,?,?,?,?)""",
                (race["race_key"], race["section"], race["source_race_name"], race["type"], config["event"]["year"],
                 config["event"]["date"], race["nominal_distance_km"], gpx_distance, config["event"]["official_results_url"]),
            )
        race_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for sequence, key in enumerate(race["checkpoints"]):
            checkpoint = checkpoints[key]
            nominal = checkpoint["nominal_cumulative_km_75"]
            if race["route_start"] == "floda":
                nominal -= checkpoints["floda"]["nominal_cumulative_km_75"]
            with conn:
                conn.execute(
                    """INSERT INTO checkpoints(race_id,checkpoint_key,name,sequence_no,nominal_distance_km,
                       is_timing_point,is_relay_exchange) VALUES(?,?,?,?,?,?,?)""",
                    (race_id, key, checkpoint["name"], sequence, nominal,
                     int(checkpoint.get("is_timing_point", True)), int(checkpoint.get("is_relay_exchange", False))),
                )
        finish_id = conn.execute(
            "SELECT id FROM checkpoints WHERE race_id=? AND checkpoint_key=?", (race_id, race["checkpoints"][-1])
        ).fetchone()[0]
        catalog[race["race_key"]] = (race_id, finish_id, gpx_distance)
    return catalog


def _raw_sources(
    race: dict[str, Any], bib: str, primary: dict[str, Any], legacy: dict[str, Any],
    cross_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]], start_index: dict[tuple[str, str], dict[str, Any]],
    public_contestant: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "primary_result_file": {"file": PRIMARY_RESULTS, "row": primary},
        "legacy_finish_export": {"file": race["source_csv"], "row": legacy},
        "public_contestant_api": {"file": str(PUBLIC_API_SNAPSHOT.relative_to(ROOT)).replace("\\", "/"), "row": public_contestant},
        "cross_validation": {},
    }
    for file_name, index in cross_indexes.items():
        match = index.get((race["source_race_name"], bib))
        if match is not None:
            payload["cross_validation"][file_name] = match
    start_match = start_index.get((str(RACE_RULES[race["race_key"]]["start_time"]), bib))
    if start_match is not None:
        payload["cross_validation"]["Startlist-77906-20260719155430.csv"] = start_match
    return payload


def _insert_results(
    conn: sqlite3.Connection, config: dict[str, Any], catalog: dict[str, tuple[int, int, float]],
    primary_by_race: dict[str, list[dict[str, Any]]], cross_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]],
    start_index: dict[tuple[str, str], dict[str, Any]], route: dict[str, Any],
    public_by_bib: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str], int], dict[tuple[str, str], int], list[dict[str, Any]]]:
    source_id = conn.execute("SELECT id FROM sources WHERE code='eqtiming_official_resultlist'").fetchone()[0]
    web_races: dict[str, Any] = {}
    report_races: dict[str, Any] = {}
    result_ids: dict[tuple[str, str], int] = {}
    team_ids: dict[tuple[str, str], int] = {}
    web_splits: list[dict[str, Any]] = []
    for race in config["races"]:
        race_key = race["race_key"]
        race_id, finish_id, gpx_distance = catalog[race_key]
        columns, legacy_rows = _legacy_rows(race)
        legacy_index = {str(row.get("Bib") or ""): row for row in legacy_rows}
        records: list[dict[str, Any]] = []
        statuses: Counter[str] = Counter()
        classes: Counter[str] = Counter()
        for primary in primary_by_race[race_key]:
            bib = str(primary.get("Startnumber") or "")
            legacy = legacy_index.get(bib)
            if legacy is None:
                raise ValueError(f"{race_key}/{bib} is missing from the legacy fallback")
            primary_status = str(primary.get("Total Time") or "").upper()
            status = primary_status if primary_status in {"DNF", "DNS", "DSQ"} else status_code(legacy.get("Status"))
            statuses[status] += 1
            class_name = official_clean(primary.get("Class")) or clean(legacy.get("ClassName"))
            if class_name:
                classes[class_name] += 1
            entity_type = "athlete" if race["type"] == "individual" else "team"
            first_name = official_clean(primary.get("Firstname")) if entity_type == "athlete" else None
            last_name = official_clean(primary.get("Surname")) if entity_type == "athlete" else None
            if entity_type == "athlete":
                published_name = official_clean(" ".join(part for part in (first_name, last_name) if part))
            else:
                published_name = official_clean(primary.get("Firstname"))
            published_name = published_name or clean(legacy.get("NameFormatted")) or "Okänd"
            listed_contact = None
            if entity_type == "team":
                listed_contact = official_clean(" ".join(filter(None, (clean(legacy.get("Firstname")), clean(legacy.get("Surname"))))))
            gross_seconds = parse_hms(primary.get("Total TimeHMS")) if status == "FINISHED" else None
            legacy_ms = to_int(legacy.get("AccumulatedTime")) if status == "FINISHED" else None
            finish_seconds = gross_seconds if gross_seconds is not None else (legacy_ms / 1000 if legacy_ms is not None else None)
            finish_ms = round(finish_seconds * 1000) if finish_seconds is not None else None
            net_ms = to_int(legacy.get("NetTime")) if status == "FINISHED" else None
            public_contestant = public_by_bib.get(bib)
            if not public_contestant:
                raise ValueError(f"Public EQ Timing snapshot is missing bib {bib}")
            public_stage = ((public_contestant.get("Pulje") or {}).get("Navn"))
            if public_stage != race["source_race_name"]:
                raise ValueError(f"Public EQ Timing race mismatch for bib {bib}: {public_stage}")
            raw = _raw_sources(race, bib, primary, legacy, cross_indexes, start_index, public_contestant)
            athlete_id = team_id = None
            if entity_type == "athlete":
                with conn:
                    conn.execute(
                        "INSERT INTO athletes(source_external_id,canonical_name,normalized_name,first_name,last_name,sex,nationality) VALUES(?,?,?,?,?,?,?)",
                        (f"result:{race_key}:{bib}", published_name, normalize(published_name), first_name, last_name,
                         official_clean(primary.get("Gender")), official_clean(primary.get("Nat"))),
                    )
                athlete_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                with conn:
                    conn.execute(
                        "INSERT INTO teams(source_external_id,team_name,normalized_name,class_name,listed_contact_name,member_list_raw) VALUES(?,?,?,?,?,?)",
                        (f"team:{race_key}:{bib}", published_name, normalize(published_name), class_name, listed_contact,
                         official_clean(primary.get("Surname"))),
                    )
                team_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                team_ids[(race_key, bib)] = team_id
            with conn:
                conn.execute(
                    """INSERT INTO results(
                       race_id,source_id,source_result_id,entity_type,athlete_id,team_id,bib,name_as_published,
                       first_name,last_name,listed_contact_name,sex,class_name,nationality,club,status,
                       finish_seconds,finish_milliseconds,gross_seconds,net_seconds,overall_place,gender_place,
                       class_place,start_time,wave_start,passing_time,role_km,raw_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (race_id, source_id, bib, entity_type, athlete_id, team_id, bib, published_name, first_name, last_name,
                     listed_contact, official_clean(primary.get("Gender")), class_name, official_clean(primary.get("Nat")),
                     official_clean(primary.get("Club")), status, finish_seconds, finish_ms, gross_seconds,
                     net_ms / 1000 if net_ms is not None else None, to_int(primary.get("Rank Total")),
                     to_int(primary.get("Rank Gender")), to_int(primary.get("Rank Class")), clean(legacy.get("Starttime")),
                     clean(legacy.get("Wavestart")), official_clean(primary.get("TimeOfDay")), to_float(legacy.get("RoleKm")),
                     json.dumps(raw, ensure_ascii=False, separators=(",", ":"))),
                )
            result_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            result_ids[(race_key, bib)] = result_id
            public_passes = _public_passes(public_contestant)
            checkpoint_ids = {
                row[0]: row[1] for row in conn.execute(
                    "SELECT checkpoint_key,id FROM checkpoints WHERE race_id=?", (race_id,)
                ).fetchall()
            }
            imported_passes = 0
            for passage in public_passes:
                station = passage.get("StasjonsOppsett") or {}
                source_name = official_clean(station.get("Navn"))
                checkpoint_key = SOURCE_POINT_KEYS.get(source_name or "")
                if checkpoint_key not in checkpoint_ids:
                    continue
                placing = passage.get("Plassering") or {}
                split = passage.get("Splitt") or {}
                elapsed = to_int(passage.get("AkkumulertTid"))
                # EQ Timing includes zero-valued placeholder passages for DNS and
                # not-yet-reached controls. They are schema slots, not timings.
                if elapsed is None or elapsed <= 0:
                    continue
                with conn:
                    conn.execute(
                        "UPDATE checkpoints SET source_station_uid=COALESCE(source_station_uid,?) WHERE id=?",
                        (str(station.get("UID") or "") or None, checkpoint_ids[checkpoint_key]),
                    )
                    conn.execute(
                        """INSERT INTO splits(result_id,checkpoint_id,elapsed_seconds,place_overall,place_gender,
                           place_class,source_point_name,split_seconds,split_distance_km,speed_kmh,pace_min_per_km,
                           passage_time,is_finish_only_export,raw_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (result_id, checkpoint_ids[checkpoint_key], elapsed / 1000, to_int(placing.get("Total")),
                         to_int(placing.get("Kjonn")), to_int(placing.get("Klasse")), source_name,
                         (to_int(split.get("Tid")) or 0) / 1000 if split.get("Tid") is not None else None,
                         to_float(split.get("Km")), to_float(split.get("Hastighet")), to_float(split.get("Tempo")),
                         official_clean(passage.get("Tid")), 0,
                         json.dumps(passage, ensure_ascii=False, separators=(",", ":"))),
                    )
                imported_passes += 1
                web_splits.append({
                    "race_key": race_key, "bib": bib, "checkpoint": checkpoint_key,
                    "elapsed_seconds": elapsed / 1000,
                    "split_seconds": (to_int(split.get("Tid")) or 0) / 1000 if split.get("Tid") is not None else None,
                    "split_distance_km": to_float(split.get("Km")), "speed_kmh": to_float(split.get("Hastighet")),
                    "pace_min_per_km": to_float(split.get("Tempo")), "passage_time": official_clean(passage.get("Tid")),
                    "place_overall": to_int(placing.get("Total")), "place_gender": to_int(placing.get("Kjonn")),
                    "place_class": to_int(placing.get("Klasse")), "source_point_name": source_name,
                    "is_finish_only_export": False,
                })
            if finish_seconds is not None and not imported_passes:
                with conn:
                    conn.execute(
                        """INSERT INTO splits(result_id,checkpoint_id,elapsed_seconds,place_overall,place_gender,
                           place_class,source_point_name,is_finish_only_export,raw_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (result_id, finish_id, finish_seconds, to_int(primary.get("Rank Total")),
                         to_int(primary.get("Rank Gender")), to_int(primary.get("Rank Class")), clean(legacy.get("PointName")),
                         1, json.dumps({"primary": primary, "legacy": legacy}, ensure_ascii=False, separators=(",", ":"))),
                    )
                web_splits.append({"race_key": race_key, "bib": bib, "checkpoint": race["checkpoints"][-1],
                                   "elapsed_seconds": finish_seconds, "source_point_name": clean(legacy.get("PointName")),
                                   "is_finish_only_export": True})
            records.append({
                "source_result_id": bib, "bib": bib, "entity_type": entity_type, "name": published_name,
                "first_name": first_name, "last_name": last_name, "listed_contact_name": listed_contact,
                "sex": official_clean(primary.get("Gender")), "class_name": class_name,
                "nation": official_clean(primary.get("Nat")), "club": official_clean(primary.get("Club")),
                "status": status, "finish_seconds": finish_seconds,
                "finish_time_formatted": official_clean(primary.get("Total Time")),
                "overall_place": to_int(primary.get("Rank Total")), "gender_place": to_int(primary.get("Rank Gender")),
                "class_place": to_int(primary.get("Rank Class")), "start_time": clean(legacy.get("Starttime")),
                "passing_time": official_clean(primary.get("TimeOfDay")), "role_km": to_float(legacy.get("RoleKm")),
                "finish_point_only": not bool(imported_passes), "split_count": imported_passes,
            })
        web_races[race_key] = {
            "race_key": race_key, "section": race["section"], "source_race_name": race["source_race_name"],
            "type": race["type"], "nominal_distance_km": race["nominal_distance_km"],
            "gpx_distance_km": gpx_distance, "records": records,
        }
        report_races[race_key] = {
            "section": race["section"], "source_race_name": race["source_race_name"], "record_count": len(records),
            "original_column_count": len(columns), "original_columns": columns, "statuses": dict(statuses),
            "classes": dict(classes),
            "point_names": sorted({clean(row.get("PointName")) for row in legacy_rows if clean(row.get("PointName"))}),
            "role_km_values": sorted({to_float(row.get("RoleKm")) for row in legacy_rows if to_float(row.get("RoleKm")) is not None}),
            "intermediate_split_rows_in_csv": sum(1 for row in legacy_rows if clean(row.get("PointName")) not in {None, "Mål"}),
            "public_api_split_rows": sum(record["split_count"] for record in records),
            "records_with_public_api_splits": sum(1 for record in records if record["split_count"] > 0),
        }
    return web_races, report_races, result_ids, team_ids, web_splits


def _insert_relay_data(
    conn: sqlite3.Connection, primary_by_race: dict[str, list[dict[str, Any]]],
    assignments_by_race: dict[str, list[dict[str, Any]]], patterns: dict[str, dict[str, Any]],
    result_ids: dict[tuple[str, str], int], team_ids: dict[tuple[str, str], int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    report: dict[str, Any] = {"event_id": 77906, "races": {}, "conflicts": []}
    web_teams: list[dict[str, Any]] = []
    web_members: list[dict[str, Any]] = []
    web_assignments: list[dict[str, Any]] = []
    for race_key in ("relay-75-2026", "relay-35-2026"):
        max_legs = int(RACE_RULES[race_key]["legs"])
        teams = {str(row["Startnumber"]): row for row in primary_by_race[race_key]}
        assignments_by_team: dict[str, list[dict[str, Any]]] = {}
        for assignment in assignments_by_race[race_key]:
            assignments_by_team.setdefault(assignment["team_bib"], []).append(assignment)
        complete = partial = without = member_count = repeated_people = 0
        for bib, team in teams.items():
            team_id = team_ids[(race_key, bib)]
            result_id = result_ids[(race_key, bib)]
            team_assignments = assignments_by_team[bib]
            members = relay_member_sources(team, team_assignments, max_legs)
            member_ids: dict[str, int] = {}
            for member in members:
                with conn:
                    conn.execute(
                        "INSERT INTO athletes(source_external_id,canonical_name,normalized_name) VALUES(?,?,?)",
                        (f"member:{race_key}:{bib}:{member['normalized_name']}", member["name"], member["normalized_name"]),
                    )
                athlete_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                member_ids[member["normalized_name"]] = athlete_id
                with conn:
                    conn.execute(
                        "INSERT INTO team_members(team_id,athlete_id,member_name_as_published,source_evidence,raw_json) VALUES(?,?,?,?,?)",
                        (team_id, athlete_id, member["name"], member["source_evidence"],
                         json.dumps(member, ensure_ascii=False, separators=(",", ":"))),
                    )
                member_count += 1
                web_members.append({"race_key": race_key, "team_bib": bib, **member})
            verified_names: list[str] = []
            for assignment in team_assignments:
                athlete_id = None
                if assignment["assignment_status"].startswith("verified_") and assignment["runner_name"]:
                    normalized_runner = normalize_name(assignment["runner_name"])
                    athlete_id = member_ids[normalized_runner]
                    verified_names.append(normalized_runner)
                with conn:
                    conn.execute(
                        """INSERT INTO relay_leg_assignments(result_id,leg_no,athlete_id,runner_name_as_published,
                           assignment_status,source_evidence,source_start_number,raw_json) VALUES(?,?,?,?,?,?,?,?)""",
                        (result_id, assignment["leg_no"], athlete_id, assignment.get("xml_runner"),
                         assignment["assignment_status"], assignment["source_evidence"], assignment["source_start_number"],
                         json.dumps({"xml": assignment.get("raw_xml"), "result_list_runner": assignment.get("result_list_runner")},
                                    ensure_ascii=False, separators=(",", ":"))),
                    )
                public_assignment = {key: value for key, value in assignment.items() if key != "raw_xml"}
                web_assignments.append(public_assignment)
                if assignment["assignment_status"] == "conflict":
                    report["conflicts"].append({
                        "race": RACE_RULES[race_key]["name"], "team": assignment["team_name"], "team_bib": bib,
                        "leg_no": assignment["leg_no"], "xml_value": assignment["xml_runner"],
                        "result_list_value": assignment["result_list_runner"], "source_evidence": assignment["source_evidence"],
                    })
            verified_count = len(verified_names)
            if verified_count == max_legs:
                complete += 1
            elif verified_count:
                partial += 1
            else:
                without += 1
            repeated_people += sum(1 for count in Counter(verified_names).values() if count > 1)
            web_teams.append({
                "race_key": race_key, "bib": bib, "team_name": official_clean(team.get("Firstname")),
                "member_list_raw": official_clean(team.get("Surname")), "team_members": members,
                "relay_leg_assignments": [
                    {key: value for key, value in assignment.items() if key != "raw_xml"}
                    for assignment in team_assignments
                ],
            })
        statuses = Counter(item["assignment_status"] for item in assignments_by_race[race_key])
        report["races"][race_key] = {
            "source_race_name": RACE_RULES[race_key]["name"], "teams": len(teams),
            "possible_leg_slots": len(teams) * max_legs,
            "verified_runner_legs": statuses["verified_xml"] + statuses["verified_xml_and_result_list"],
            "verified_xml": statuses["verified_xml"],
            "verified_xml_and_result_list": statuses["verified_xml_and_result_list"],
            "missing": statuses["missing"], "conflicts": statuses["conflict"],
            "complete_teams": complete, "partial_teams": partial, "teams_without_mapping": without,
            "unique_team_members": member_count, "people_running_multiple_legs": repeated_people,
            "code_pattern_verification": patterns[race_key],
        }
    return report, web_teams, web_members, web_assignments


def _write_reports(
    files_analysis: dict[str, Any], relay_report: dict[str, Any], report: dict[str, Any]
) -> None:
    write_json(ROOT / "reports" / "eqtiming-files-analysis.json", files_analysis)
    file_md = [
        "# EQ Timing file analysis", "", f"Primary results: `{PRIMARY_RESULTS}`", "",
        f"Primary relay leg evidence: `{PRIMARY_RELAY_LEGS}`", "",
        "| File | Format | Records | Fields | Races | Members | Leg codes | Splits |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for item in files_analysis["files"]:
        file_md.append(
            f"| {item['file_name']} | {item['format']} | "
            f"{item['record_count'] if item['record_count'] is not None else 'n/a'} | "
            f"{item['field_count'] if item['field_count'] is not None else 'n/a'} | "
            f"{', '.join(item['races']) or 'n/a'} | {'yes' if item['contains_relay_members'] else 'no'} | "
            f"{'yes' if item['contains_leg_encoding'] else 'no'} | "
            f"{'yes' if item['contains_intermediate_splits'] else 'no'} |"
        )
    (ROOT / "reports" / "eqtiming-files-analysis.md").write_text("\n".join(file_md) + "\n", encoding="utf-8")

    write_json(ROOT / "reports" / "relay-member-import-report.json", relay_report)
    relay_md = ["# Relay member import", ""]
    for item in relay_report["races"].values():
        relay_md.extend([
            f"## {item['source_race_name']}", "", f"- Teams: {item['teams']}",
            f"- Verified runner-to-leg assignments: {item['verified_runner_legs']}",
            f"- Missing: {item['missing']}", f"- Conflicts: {item['conflicts']}",
            f"- Complete / partial / none: {item['complete_teams']} / {item['partial_teams']} / {item['teams_without_mapping']}",
            f"- Unique team members: {item['unique_team_members']}", "",
        ])
    if relay_report["conflicts"]:
        relay_md.extend(["## Conflicts", ""])
        relay_md.extend(
            f"- {item['race']} bib {item['team_bib']} leg {item['leg_no']}: XML `{item['xml_value']}`, result list `{item['result_list_value']}`"
            for item in relay_report["conflicts"]
        )
    (ROOT / "reports" / "relay-member-import-report.md").write_text("\n".join(relay_md) + "\n", encoding="utf-8")

    write_json(
        ROOT / "reports" / "eqtiming-missing-data.json",
        {
            "event_id": 77906,
            "intermediate_splits_found": True,
            "available": "Official cumulative passages, split times, pace, speed and placings from EQ Timing's public contestant endpoint.",
            "known_limitations": [
                "DNS records and some DNF records have no or incomplete passages.",
                "Nolhaga is a timing point, not a relay exchange.",
                "A relay runner is attached to a leg only when separate start-list evidence verifies the mapping.",
            ],
            "rule": "No missing split, passing, leg time, or placing is interpolated or fabricated.",
        },
    )
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def import_all_official() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    route = load_route(config)
    WEB_ROUTE.parent.mkdir(parents=True, exist_ok=True)
    WEB_ROUTE.write_text(json.dumps(route, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    primary_rows = load_primary_results()
    public_by_bib = _load_public_contestants()
    primary_by_race = {
        race["race_key"]: [row for row in primary_rows if row.get("Stage") == race["source_race_name"]]
        for race in config["races"]
    }
    for race_key, expected in EXPECTED_COUNTS.items():
        actual = len(primary_by_race[race_key])
        if actual != expected:
            raise ValueError(f"{PRIMARY_RESULTS}: {race_key} has {actual}, expected {expected}")

    xml_rows = load_xml_starts()
    assignments_by_race: dict[str, list[dict[str, Any]]] = {}
    patterns: dict[str, dict[str, Any]] = {}
    for race_key in ("relay-75-2026", "relay-35-2026"):
        assignments, pattern = build_relay_assignments(race_key, primary_by_race[race_key], xml_rows)
        if not pattern["verified"]:
            raise ValueError(f"Relay code pattern was not verified for {race_key}: {pattern}")
        assignments_by_race[race_key] = assignments
        patterns[race_key] = pattern

    cross_indexes, start_index = _cross_validation_indexes()
    conn = prepare_db()
    catalog = _insert_catalog(conn, config, route)
    web_races, report_races, result_ids, team_ids, web_splits = _insert_results(
        conn, config, catalog, primary_by_race, cross_indexes, start_index, route, public_by_bib
    )
    relay_report, web_teams, web_members, web_assignments = _insert_relay_data(
        conn, primary_by_race, assignments_by_race, patterns, result_ids, team_ids
    )
    conn.commit()
    conn.close()

    report = {
        "event": config["event"], "primary_result_source": PRIMARY_RESULTS,
        "primary_relay_leg_source": PRIMARY_RELAY_LEGS,
        "route": {"point_count": route["point_count"], "full_distance_km": route["full_distance_km"],
                  "floda_start": route["floda_start"]},
        "races": report_races,
        "limitations": [
            "CSV exports contain finish results only; official passages come from the cached public EQ Timing endpoint.",
            "Empty XML leg names are stored as missing and conflicts are never verified assignments.",
            "Missing passages are retained as missing and never interpolated.",
            "All original fields from CSV, XML and public JSON sources are preserved in raw_json.",
        ],
    }
    files_analysis = analyze_source_files()
    _write_reports(files_analysis, relay_report, report)
    web_payload = {
        "meta": {
            "project": "Gotaleden Splits", "event": config["event"],
            "primary_result_source": PRIMARY_RESULTS, "primary_relay_leg_source": PRIMARY_RELAY_LEGS,
            "public_api_source": str(PUBLIC_API_SNAPSHOT.relative_to(ROOT)).replace("\\", "/"),
            "raw_fields_preserved": True, "intermediate_splits_available": True,
            "relay_coverage": relay_report["races"],
        },
        "checkpoints": {
            race["race_key"]: [
                {
                    "key": key,
                    "name": next(item["name"] for item in config["checkpoints"] if item["key"] == key),
                    "distance_km": next(item["nominal_cumulative_km_75"] for item in config["checkpoints"] if item["key"] == key)
                        - (41.5 if race["route_start"] == "floda" else 0),
                    "is_timing_point": next(item.get("is_timing_point", True) for item in config["checkpoints"] if item["key"] == key),
                    "is_relay_exchange": next(item.get("is_relay_exchange", False) for item in config["checkpoints"] if item["key"] == key),
                }
                for key in race["checkpoints"]
            ]
            for race in config["races"]
        },
        "races": web_races, "splits": web_splits, "teams": web_teams,
        "team_members": web_members, "relay_leg_assignments": web_assignments,
    }
    WEB_RESULTS.write_text(json.dumps(web_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "races": {key: value["record_count"] for key, value in report_races.items()},
        "relay": relay_report["races"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import_all_official()
