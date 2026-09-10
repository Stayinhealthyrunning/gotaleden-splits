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
    REPORT_COMPAT,
    ROOT,
    WEB_RESULTS,
    WEB_RESULTS_COMPAT,
    WEB_ROUTE,
    clean,
    normalize,
    prepare_db,
    status_code,
    to_float,
    to_int,
    write_payload,
)
from eqtiming_official_import import (
    analyze_source_files,
    bind_primary_results,
    build_relay_assignments,
    clean as official_clean,
    eqtiming_source_context,
    load_primary_results,
    load_xml_starts,
    normalize_name,
    parse_hms,
    person_identity_evidence,
    read_csv_file,
    relay_member_sources,
    source_dir,
    write_json,
)
from course_versions import (
    CourseConfigError,
    race_course_geometry,
    resolve_all_courses,
    web_course_catalog,
)
from gpx_analysis import build_gpx_artifacts
from identity import IdentityConflictError, external_identity_row, resolve_person_identity
from source_bindings import dispatch_source_groups, group_source_bindings, race_catalog, race_contract, resolve_source_bindings, web_race_catalog

def _load_public_contestants(source_event: dict[str, Any]) -> dict[str, dict[str, Any]]:
    snapshot = ROOT / source_event["public_snapshot"]
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    contestants = payload.get("contestants", {})
    expected = int(source_event["expected_records"])
    if payload.get("event_id") != source_event["event_id"] or payload.get("response_count") != expected or not payload.get("passes_included"):
        raise ValueError(f"Incomplete public EQ Timing snapshot: {snapshot}")
    return {str(key): value for key, value in contestants.items()}


def _public_passes(contestant: dict[str, Any]) -> list[dict[str, Any]]:
    legs = contestant.get("EtappeDeltaker") or {}
    passages: list[dict[str, Any]] = []
    for leg in legs.values():
        passages.extend((leg.get("Passeringer") or {}).values())
    return sorted(passages, key=lambda item: int((item.get("StasjonsOppsett") or {}).get("Sortering") or 0))


def _find_or_create_athlete(
    conn: sqlite3.Connection, identity: dict[str, Any], *, source_external_id: str,
    canonical_name: str, normalized_name: str, first_name: str | None = None,
    last_name: str | None = None, sex: str | None = None, nationality: str | None = None,
    age: int | None = None, birth_year: int | None = None, public_uid: int | None = None,
) -> int:
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO athletes(person_key,identity_status,identity_scope,source_external_id,
               public_contestant_uid,canonical_name,normalized_name,first_name,last_name,sex,nationality,age,birth_year)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (identity["person_key"], identity["status"], identity["scope"], source_external_id, public_uid,
             canonical_name, normalized_name, first_name, last_name, sex, nationality, age, birth_year),
        )
    row = conn.execute("SELECT id FROM athletes WHERE person_key=?", (identity["person_key"],)).fetchone()
    if row is None:
        raise IdentityConflictError(f"Could not resolve canonical person {identity['person_key']}")
    return int(row[0])


def _register_external_identity(
    conn: sqlite3.Connection, athlete_id: int, evidence: dict[str, Any], *, race_key: str, source_event_key: str,
) -> None:
    row = external_identity_row(
        evidence, athlete_id=athlete_id, race_key=race_key, source_event_key=source_event_key,
    )
    existing = conn.execute("SELECT athlete_id FROM athlete_external_ids WHERE identity_namespace=?", (row[-1],)).fetchone()
    if existing and int(existing[0]) != athlete_id:
        raise IdentityConflictError(f"Verified identity namespace {row[-1]!r} points to multiple canonical people")
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO athlete_external_ids(athlete_id,provider,id_type,identity_scope,scope_key,
               external_id,confidence,evidence,identity_namespace) VALUES(?,?,?,?,?,?,?,?,?)""",
            row,
        )


def _legacy_rows(binding: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    with (ROOT / binding["legacy_csv"]).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _cross_validation_indexes(source_event: dict[str, Any]) -> tuple[dict[str, dict[tuple[str, str], dict[str, Any]]], dict[tuple[str, str], dict[str, Any]]]:
    directory = source_dir(source_event)
    primary_results = source_event["primary_results"]
    result_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for file_name in source_event["result_list_files"]:
        if file_name == primary_results:
            continue
        _, rows = read_csv_file(directory / file_name, ";")
        result_indexes[file_name] = {
            (str(row.get("Race") or ""), str(row.get("Startnumber") or "")): row for row in rows
        }
    start_rows: list[dict[str, Any]] = []
    if source_event.get("start_cross_validation_file"):
        _, start_rows = read_csv_file(directory / source_event["start_cross_validation_file"], "\t")
    start_index = {(str(row.get("Start Time") or ""), str(row.get("BIB") or "")): row for row in start_rows}
    return result_indexes, start_index


def _insert_source_event(conn: sqlite3.Connection, source_event_key: str, source_event: dict[str, Any]) -> dict[str, int]:
    rows = [
        ("official_resultlist", "eqtiming", source_event_key, source_event["primary_results"], source_event["results_url"], "csv"),
        ("legacy_csv", "eqtiming", source_event_key, "EQ Timing finish exports", source_event["results_url"], "csv"),
        ("public_api", "eqtiming", source_event_key, "EQ Timing public contestant snapshot", source_event["contestants_endpoint"] + "?passes=true", "json"),
    ]
    if source_event.get("primary_relay_legs"):
        rows.append(("relay_startlist", "eqtiming", source_event_key, source_event["primary_relay_legs"], source_event["results_url"], "xml"))
    with conn:
        conn.executemany(
            "INSERT INTO sources(code,provider,source_event_key,name,base_url,source_type) VALUES(?,?,?,?,?,?)", rows
        )
    return {
        row[0]: row[1]
        for row in conn.execute("SELECT code,id FROM sources WHERE provider=? AND source_event_key=?", ("eqtiming", source_event_key))
    }


def _insert_catalog(
    conn: sqlite3.Connection, config: dict[str, Any], courses: dict[str, dict[str, Any]],
) -> tuple[dict[str, tuple[int, int | None, float | None]], dict[str, dict[str, Any]]]:
    bindings = resolve_source_bindings(config)
    catalog: dict[str, tuple[int, int | None, float | None]] = {}
    geometries: dict[str, dict[str, Any]] = {}
    with conn:
        for key, course in courses.items():
            definition = course["definition"]
            conn.execute(
                """INSERT INTO course_versions(course_version,event_key,fingerprint,route_source,
                   elevation_reference_source,whole_course_comparison_group,route_asset,elevation_asset,raw_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (key, course["event_key"], course["fingerprint"], definition["route_source"],
                 definition.get("elevation_reference_source"), course.get("whole_course_comparison_group"),
                 f"data/courses/{key}/route.json", f"data/courses/{key}/elevation.json",
                 json.dumps(definition, ensure_ascii=False, separators=(",", ":"))),
            )
    for race in race_catalog(config):
        resolved = bindings.get(race["race_key"])
        binding = resolved["source_race"] if resolved else None
        contract = race_contract(config, race)
        course = courses.get(race.get("course_version"))
        if course is None:
            raise CourseConfigError(f"Race {race['race_key']!r} references unknown CourseVersion {race.get('course_version')!r}")
        geometry = race_course_geometry(race, course)
        geometries[race["race_key"]] = geometry
        gpx_distance = geometry["gpx_distance_km"]
        with conn:
            conn.execute(
                """INSERT INTO races(race_key,event_key,race_family,course_version,data_status,is_analyzable,source_event_key,
                   section_name,source_race_name,race_type,participant_entity,competition_format,team_structure_json,
                   capabilities_json,presentation_json,class_scheme,year,race_date,nominal_distance_km,gpx_distance_km,
                   route_start_distance_km,route_end_distance_km,official_url)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (race["race_key"], config["event"]["event_key"], race["race_family"], race.get("course_version"),
                 race["data_status"], 0, resolved["source_event_key"] if resolved else None, race["section"],
                 binding["source_race_name"] if binding else None, race["type"], contract["participant"]["entity"],
                 contract["competition"]["format"], json.dumps(contract["competition"]["team_structure"], ensure_ascii=False),
                 json.dumps(contract["capabilities"], ensure_ascii=False), json.dumps(contract["presentation"], ensure_ascii=False),
                 contract["class_scheme"], race["year"], race.get("race_date"),
                 race.get("nominal_distance_km"), gpx_distance, geometry["start_route_distance_km"],
                 geometry["end_route_distance_km"],
                 resolved["source_event"].get("results_url") if resolved else None),
            )
        race_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        start_nominal = float(geometry["checkpoints"][0]["nominal_distance_km"])
        segments = {item["from"]: item for item in course["segments"]}
        for sequence, checkpoint in enumerate(geometry["checkpoints"]):
            key = checkpoint["key"]
            nominal = float(checkpoint["nominal_distance_km"]) - start_nominal
            route_distance = checkpoint["route_distance_km"]
            segment = segments.get(key)
            with conn:
                conn.execute(
                    """INSERT INTO checkpoints(race_id,checkpoint_key,name,sequence_no,nominal_distance_km,
                       route_distance_km,is_timing_point,is_relay_exchange,timing_only,analysis_boundary,
                       replay_anchor,speaker_checkpoint,segment_key_to_next,segment_comparison_key_to_next)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (race_id, key, checkpoint["name"], sequence, nominal, route_distance,
                     int(checkpoint.get("is_timing_point", True)), int(checkpoint.get("is_relay_exchange", False)),
                     int(checkpoint.get("timing_only", False)), int(checkpoint.get("analysis_boundary", True)),
                     int(checkpoint.get("replay_anchor", True)), int(checkpoint.get("speaker_checkpoint", False)),
                     segment.get("key") if segment else None, segment.get("comparison_key") if segment else None),
                )
        finish_id = None
        if geometry["checkpoints"]:
            finish_id = conn.execute(
                "SELECT id FROM checkpoints WHERE race_id=? AND checkpoint_key=?", (race_id, geometry["checkpoints"][-1]["key"])
            ).fetchone()[0]
        catalog[race["race_key"]] = (race_id, finish_id, gpx_distance)
    return catalog, geometries


def _raw_sources(
    binding: dict[str, Any], source_event: dict[str, Any], bib: str, primary: dict[str, Any], legacy: dict[str, Any],
    cross_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]], start_index: dict[tuple[str, str], dict[str, Any]],
    public_contestant: dict[str, Any],
) -> dict[str, Any]:
    primary_results = source_event["primary_results"]
    snapshot = str(source_event["public_snapshot"])
    payload: dict[str, Any] = {
        "primary_result_file": {"file": primary_results, "row": primary},
        "legacy_finish_export": {"file": binding["legacy_csv"], "row": legacy},
        "public_contestant_api": {"file": snapshot.replace("\\", "/"), "row": public_contestant},
        "cross_validation": {},
    }
    for file_name, index in cross_indexes.items():
        match = index.get((binding["source_race_name"], bib))
        if match is not None:
            payload["cross_validation"][file_name] = match
    start_match = start_index.get((str(binding["start_time"]), bib))
    if start_match is not None:
        payload["cross_validation"][source_event["start_cross_validation_file"]] = start_match
    return payload


def _insert_results(
    conn: sqlite3.Connection, config: dict[str, Any], catalog: dict[str, tuple[int, int | None, float | None]],
    primary_by_race: dict[str, list[dict[str, Any]]], cross_indexes: dict[str, dict[tuple[str, str], dict[str, Any]]],
    start_index: dict[tuple[str, str], dict[str, Any]],
    public_by_bib: dict[str, dict[str, Any]], source_event: dict[str, Any],
    bindings: dict[str, dict[str, Any]], source_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str], int], dict[tuple[str, str], int], list[dict[str, Any]]]:
    web_races: dict[str, Any] = {}
    report_races: dict[str, Any] = {}
    result_ids: dict[tuple[str, str], int] = {}
    team_ids: dict[tuple[str, str], int] = {}
    web_splits: list[dict[str, Any]] = []
    for resolved in bindings.values():
        race = resolved["race"]
        contract = race_contract(config, race)
        class_definitions = {item["source_name"]: item for item in contract["class_metadata"]["classes"]}
        race_key = race["race_key"]
        binding = bindings[race_key]["source_race"]
        race_id, finish_id, gpx_distance = catalog[race_key]
        route_start_distance, route_end_distance = conn.execute(
            "SELECT route_start_distance_km,route_end_distance_km FROM races WHERE id=?", (race_id,)
        ).fetchone()
        if finish_id is None or gpx_distance is None:
            raise SourceBindingError(f"Importable race {race_key} has no complete course/checkpoint geometry")
        columns, legacy_rows = _legacy_rows(binding)
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
            class_definition = class_definitions.get(class_name, {})
            if class_name:
                classes[class_name] += 1
            entity_type = "athlete" if contract["participant"]["entity"] == "person" else "team"
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
            if public_stage != binding["source_race_name"]:
                raise ValueError(f"Public EQ Timing race mismatch for bib {bib}: {public_stage}")
            public_athlete = public_contestant.get("Utover") or {}
            public_class = public_contestant.get("Klasse") or {}
            public_uid = to_int(public_contestant.get("UID"))
            age = to_int(public_contestant.get("Alder")) or to_int(public_athlete.get("Alder"))
            birth_year = to_int(public_athlete.get("Aar"))
            class_ranked_raw = public_class.get("Rangering")
            class_is_ranked = None if class_ranked_raw is None else int(bool(class_ranked_raw))
            club = (
                official_clean(primary.get("Club"))
                or official_clean(public_contestant.get("Klubbnavn"))
                or official_clean(public_athlete.get("Klubbnavn"))
            )
            raw = _raw_sources(binding, source_event, bib, primary, legacy, cross_indexes, start_index, public_contestant)
            athlete_id = team_id = None
            identity = None
            if entity_type == "athlete":
                evidence = person_identity_evidence(public_contestant, source_event)
                identity = resolve_person_identity(
                    evidence, race_key=race_key, source_event_key=resolved["source_event_key"], local_result_id=bib,
                )
                athlete_id = _find_or_create_athlete(
                    conn, identity, source_external_id=f"result:{race_key}:{bib}", canonical_name=published_name,
                    normalized_name=normalize(published_name), first_name=first_name, last_name=last_name,
                    sex=official_clean(primary.get("Gender")), nationality=official_clean(primary.get("Nat")),
                    age=age, birth_year=birth_year, public_uid=public_uid,
                )
                for item in evidence:
                    _register_external_identity(
                        conn, athlete_id, item, race_key=race_key, source_event_key=resolved["source_event_key"],
                    )
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
                       class_place,start_time,wave_start,passing_time,role_km,public_contestant_uid,age,birth_year,
                       class_is_ranked,raw_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (race_id, source_id, bib, entity_type, athlete_id, team_id, bib, published_name, first_name, last_name,
                     listed_contact, official_clean(primary.get("Gender")), class_name, official_clean(primary.get("Nat")),
                     club, status, finish_seconds, finish_ms, gross_seconds,
                     net_ms / 1000 if net_ms is not None else None, to_int(primary.get("Rank Total")),
                     to_int(primary.get("Rank Gender")), to_int(primary.get("Rank Class")), clean(legacy.get("Starttime")),
                     clean(legacy.get("Wavestart")), official_clean(primary.get("TimeOfDay")), to_float(legacy.get("RoleKm")),
                     public_uid, age, birth_year, class_is_ranked,
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
                checkpoint_key = source_event["checkpoint_map"].get(source_name or "")
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
                           place_class,split_place_overall,split_place_gender,split_place_class,source_point_name,
                           source_station_uid,split_seconds,split_distance_km,source_checkpoint_distance_km,
                           speed_kmh,pace_min_per_km,split_speed_kmh,split_pace_min_per_km,cumulative_speed_kmh,
                           cumulative_pace_min_per_km,passage_time,is_finish_only_export,raw_json)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (result_id, checkpoint_ids[checkpoint_key], elapsed / 1000, to_int(placing.get("Total")),
                         to_int(placing.get("Kjonn")), to_int(placing.get("Klasse")),
                         to_int(placing.get("SplittTotal")), to_int(placing.get("SplittKjonn")),
                         to_int(placing.get("SplittKlasse")), source_name, str(station.get("UID") or "") or None,
                         (to_int(split.get("Tid")) or 0) / 1000 if split.get("Tid") is not None else None,
                         to_float(split.get("Km")), to_float(station.get("Km")),
                         to_float(split.get("Hastighet")), to_float(split.get("Tempo")),
                         to_float(split.get("Hastighet")), to_float(split.get("Tempo")),
                         to_float(split.get("TotalHastighet")), to_float(split.get("TotalTempo")),
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
                    "split_place_overall": to_int(placing.get("SplittTotal")),
                    "split_place_gender": to_int(placing.get("SplittKjonn")),
                    "split_place_class": to_int(placing.get("SplittKlasse")),
                    "source_station_uid": str(station.get("UID") or "") or None,
                    "source_checkpoint_distance_km": to_float(station.get("Km")),
                    "split_speed_kmh": to_float(split.get("Hastighet")),
                    "split_pace_min_per_km": to_float(split.get("Tempo")),
                    "cumulative_speed_kmh": to_float(split.get("TotalHastighet")),
                    "cumulative_pace_min_per_km": to_float(split.get("TotalTempo")),
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
                web_splits.append({"race_key": race_key, "bib": bib, "checkpoint": race["checkpoint_keys"][-1],
                                   "elapsed_seconds": finish_seconds, "source_point_name": clean(legacy.get("PointName")),
                                   "is_finish_only_export": True})
            records.append({
                "source_result_id": bib, "bib": bib, "entity_type": entity_type, "name": published_name,
                "person_key": identity["person_key"] if identity else None,
                "identity_status": identity["status"] if identity else None,
                "identity_scope": identity["scope"] if identity else None,
                "first_name": first_name, "last_name": last_name, "listed_contact_name": listed_contact,
                "sex": official_clean(primary.get("Gender")), "class_name": class_name,
                "nation": official_clean(primary.get("Nat")), "club": club,
                "public_contestant_uid": public_uid, "age": age, "birth_year": birth_year,
                "class_is_ranked": None if class_is_ranked is None else bool(class_is_ranked),
                "class_competition_type": class_definition.get("competition_type", "competitive"),
                "status": status, "finish_seconds": finish_seconds,
                "finish_time_formatted": official_clean(primary.get("Total Time")),
                "overall_place": to_int(primary.get("Rank Total")), "gender_place": to_int(primary.get("Rank Gender")),
                "class_place": to_int(primary.get("Rank Class")), "start_time": clean(legacy.get("Starttime")),
                "passing_time": official_clean(primary.get("TimeOfDay")), "role_km": to_float(legacy.get("RoleKm")),
                "finish_point_only": not bool(imported_passes), "split_count": imported_passes,
            })
        web_races[race_key] = {
            "race_key": race_key, "section": race["section"], "source_race_name": binding["source_race_name"],
            "event_key": config["event"]["event_key"], "race_family": race["race_family"],
            "year": race["year"], "race_date": race.get("race_date"), "course_version": race.get("course_version"),
            "data_status": race["data_status"], "source_event_key": resolved["source_event_key"], "analyzable": True,
            "type": race["type"], "nominal_distance_km": race["nominal_distance_km"],
            **contract,
            "gpx_distance_km": gpx_distance, "route_start_distance_km": route_start_distance,
            "route_end_distance_km": route_end_distance, "records": records,
        }
        report_races[race_key] = {
            "section": race["section"], "source_race_name": binding["source_race_name"], "record_count": len(records),
            "original_column_count": len(columns), "original_columns": columns, "statuses": dict(statuses),
            "classes": dict(classes),
            "point_names": sorted({clean(row.get("PointName")) for row in legacy_rows if clean(row.get("PointName"))}),
            "role_km_values": sorted({to_float(row.get("RoleKm")) for row in legacy_rows if to_float(row.get("RoleKm")) is not None}),
            "intermediate_split_rows_in_csv": sum(1 for row in legacy_rows if clean(row.get("PointName")) not in {None, "Mål"}),
            "public_api_split_rows": sum(record["split_count"] for record in records),
            "records_with_public_api_splits": sum(1 for record in records if record["split_count"] > 0),
        }
        with conn:
            conn.execute("UPDATE races SET is_analyzable=1 WHERE id=?", (race_id,))
    return web_races, report_races, result_ids, team_ids, web_splits


def _insert_relay_data(
    conn: sqlite3.Connection, primary_by_race: dict[str, list[dict[str, Any]]],
    assignments_by_race: dict[str, list[dict[str, Any]]], patterns: dict[str, dict[str, Any]],
    result_ids: dict[tuple[str, str], int], team_ids: dict[tuple[str, str], int],
    source_event: dict[str, Any], bindings: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    report: dict[str, Any] = {"event_id": source_event["event_id"], "races": {}, "conflicts": []}
    web_teams: list[dict[str, Any]] = []
    web_members: list[dict[str, Any]] = []
    web_assignments: list[dict[str, Any]] = []
    relay_bindings = {key: item for key, item in bindings.items() if isinstance(item["source_race"].get("relay"), dict)}
    for race_key, resolved in relay_bindings.items():
        binding = resolved["source_race"]
        max_legs = int(binding["relay"]["legs"])
        teams = {str(row["Startnumber"]): row for row in primary_by_race[race_key]}
        assignments_by_team: dict[str, list[dict[str, Any]]] = {}
        for assignment in assignments_by_race[race_key]:
            assignments_by_team.setdefault(assignment["team_bib"], []).append(assignment)
        complete = partial = without = member_count = repeated_people = 0
        for bib, team in teams.items():
            team_id = team_ids[(race_key, bib)]
            result_id = result_ids[(race_key, bib)]
            team_assignments = assignments_by_team[bib]
            members = relay_member_sources(team, team_assignments, max_legs, source_event)
            member_ids: dict[str, int] = {}
            for member in members:
                local_id = f"team-member:{bib}:{member['normalized_name']}"
                identity = resolve_person_identity(
                    [], race_key=race_key, source_event_key=resolved["source_event_key"], local_result_id=local_id,
                )
                athlete_id = _find_or_create_athlete(
                    conn, identity, source_external_id=f"member:{race_key}:{bib}:{member['normalized_name']}",
                    canonical_name=member["name"], normalized_name=member["normalized_name"],
                )
                member_ids[member["normalized_name"]] = athlete_id
                with conn:
                    conn.execute(
                        "INSERT INTO team_members(team_id,athlete_id,member_name_as_published,source_evidence,raw_json) VALUES(?,?,?,?,?)",
                        (team_id, athlete_id, member["name"], member["source_evidence"],
                         json.dumps(member, ensure_ascii=False, separators=(",", ":"))),
                    )
                member_count += 1
                web_members.append({
                    "race_key": race_key, "team_bib": bib, "name": member["name"],
                    "person_key": identity["person_key"], "identity_status": identity["status"],
                    "identity_scope": identity["scope"],
                })
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
                        "race": binding["source_race_name"], "team": assignment["team_name"], "team_bib": bib,
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
                "team_members": [{"name": member["name"]} for member in members],
            })
        statuses = Counter(item["assignment_status"] for item in assignments_by_race[race_key])
        report["races"][race_key] = {
            "source_race_name": binding["source_race_name"], "teams": len(teams),
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


def _write_split_coverage(
    config: dict[str, Any], web_races: dict[str, Any], web_splits: list[dict[str, Any]],
    source_event_key: str, source_event: dict[str, Any], bindings: dict[str, dict[str, Any]],
    compatibility: bool = False,
) -> dict[str, Any]:
    split_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for split in web_splits:
        split_index.setdefault((split["race_key"], split["bib"]), []).append(split)
    report: dict[str, Any] = {
        "event_id": source_event["event_id"],
        "positive_passage_rule": "elapsed_seconds > 0",
        "finish_comparison_tolerance_seconds": 2.0,
        "races": {},
    }
    for resolved in bindings.values():
        race = resolved["race"]
        race_key = race["race_key"]
        course_definition = config["course_versions"][race["course_version"]]
        checkpoint_catalog = {
            item["key"]: item for item in config["checkpoint_catalogs"][course_definition["checkpoint_catalog"]]
        }
        records = web_races[race_key]["records"]
        required = [
            key for index, key in enumerate(race["checkpoint_keys"])
            if index > 0 and checkpoint_catalog[key].get("is_timing_point", True)
        ]
        status_counts = Counter(record["status"] for record in records)
        with_passages = complete = partial = finished_complete = finished_missing = 0
        finished_finish = dnf_with = dns_with = 0
        missing = Counter()
        extra_status_records: list[dict[str, Any]] = []
        finish_differences: list[dict[str, Any]] = []
        monotonic_anomalies: list[dict[str, Any]] = []
        for record in records:
            splits = sorted(split_index.get((race_key, record["bib"]), []), key=lambda item: item["elapsed_seconds"])
            keys = {item["checkpoint"] for item in splits}
            has_passage = bool(splits)
            is_complete = all(key in keys for key in required)
            if has_passage:
                with_passages += 1
            if is_complete:
                complete += 1
            elif has_passage:
                partial += 1
            for key in required:
                if key not in keys:
                    missing[key] += 1
            if record["status"] == "FINISHED":
                finished_complete += int(is_complete)
                finished_missing += int(not is_complete)
                finish_split = next((item for item in splits if item["checkpoint"] == race["checkpoint_keys"][-1]), None)
                if finish_split:
                    finished_finish += 1
                    difference = finish_split["elapsed_seconds"] - record["finish_seconds"]
                    if abs(difference) > 2.0:
                        finish_differences.append({"bib": record["bib"], "name": record["name"], "difference_seconds": round(difference, 3)})
            elif record["status"] == "DNF" and has_passage:
                dnf_with += 1
            elif record["status"] == "DNS" and has_passage:
                dns_with += 1
            if record["status"] not in {"FINISHED", "DNF"} and has_passage:
                extra_status_records.append({"bib": record["bib"], "name": record["name"], "status": record["status"], "passage_count": len(splits)})
            ordered_by_checkpoint = sorted(splits, key=lambda item: race["checkpoint_keys"].index(item["checkpoint"]))
            if any(second["elapsed_seconds"] < first["elapsed_seconds"] for first, second in zip(ordered_by_checkpoint, ordered_by_checkpoint[1:])):
                monotonic_anomalies.append({"bib": record["bib"], "name": record["name"]})
        report["races"][race_key] = {
            "result_count": len(records),
            "status_counts": {
                "FINISHED": status_counts["FINISHED"], "DNF": status_counts["DNF"], "DNS": status_counts["DNS"],
                "other": sum(count for status, count in status_counts.items() if status not in {"FINISHED", "DNF", "DNS"}),
            },
            "required_checkpoint_series": required,
            "results_with_positive_passage": with_passages,
            "complete_checkpoint_series": complete,
            "partial_checkpoint_series": partial,
            "finished_with_complete_series": finished_complete,
            "finished_missing_checkpoints": finished_missing,
            "finished_with_finish_passage": finished_finish,
            "dnf_with_passages": dnf_with,
            "dns_with_positive_passages": dns_with,
            "missing_passages_by_checkpoint": {key: missing[key] for key in required},
            "imported_passages": sum(len(split_index.get((race_key, record["bib"]), [])) for record in records),
            "positive_passages_with_status_other_than_finished_or_dnf": extra_status_records,
            "finish_time_comparison": {
                "compared": finished_finish,
                "differences_over_tolerance": len(finish_differences),
                "difference_samples": finish_differences[:25],
            },
            "non_monotonic_elapsed_results": monotonic_anomalies,
        }
    report_path = ROOT / "reports" / f"{source_event_key}-split-coverage.json"
    write_json(report_path, report)
    if compatibility:
        write_json(ROOT / "reports" / "eqtiming-split-coverage.json", report)
    lines = ["# EQ Timing split coverage", "", "Only passages with `elapsed_seconds > 0` are counted.", "",
             "| Race | Results | FINISHED | DNF | DNS | With passage | Complete | Partial | Passages |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for race_key, item in report["races"].items():
        status = item["status_counts"]
        lines.append(f"| {race_key} | {item['result_count']} | {status['FINISHED']} | {status['DNF']} | {status['DNS']} | {item['results_with_positive_passage']} | {item['complete_checkpoint_series']} | {item['partial_checkpoint_series']} | {item['imported_passages']} |")
    for race_key, resolved in bindings.items():
        title = resolved["source_race"].get("coverage_report_title")
        if title:
            item = report["races"][race_key]
            status = item["status_counts"]
            lines.extend(["", f"## {title}", "",
                          f"The {item['results_with_positive_passage']} records with positive passages comprise "
                          f"{status['FINISHED']} FINISHED, {status['DNF']} DNF and {item['dns_with_positive_passages']} DNS. "
                          "Status is preserved from the official result source.", ""])
    for race_key, item in report["races"].items():
        lines.extend([f"## {race_key}", "",
                      f"- FINISHED missing one or more checkpoints: {item['finished_missing_checkpoints']}",
                      f"- FINISHED with Mål passage: {item['finished_with_finish_passage']}",
                      f"- Finish-time differences over 2 s: {item['finish_time_comparison']['differences_over_tolerance']}",
                      f"- Non-monotonic elapsed sequences: {len(item['non_monotonic_elapsed_results'])}", ""])
    markdown = "\n".join(lines)
    (ROOT / "reports" / f"{source_event_key}-split-coverage.md").write_text(markdown, encoding="utf-8")
    if compatibility:
        (ROOT / "reports" / "eqtiming-split-coverage.md").write_text(markdown, encoding="utf-8")
    return report


def _write_reports(
    files_analysis: dict[str, Any], relay_report: dict[str, Any], report: dict[str, Any],
    source_event_key: str, source_event: dict[str, Any], compatibility: bool = False,
) -> None:
    primary_results = source_event["primary_results"]
    primary_relay_legs = source_event.get("primary_relay_legs") or "n/a"
    write_json(ROOT / "reports" / f"{source_event_key}-files-analysis.json", files_analysis)
    if compatibility:
        write_json(ROOT / "reports" / "eqtiming-files-analysis.json", files_analysis)
    file_md = [
        "# EQ Timing file analysis", "", f"Primary results: `{primary_results}`", "",
        f"Primary relay leg evidence: `{primary_relay_legs}`", "",
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
    file_markdown = "\n".join(file_md) + "\n"
    (ROOT / "reports" / f"{source_event_key}-files-analysis.md").write_text(file_markdown, encoding="utf-8")
    if compatibility:
        (ROOT / "reports" / "eqtiming-files-analysis.md").write_text(file_markdown, encoding="utf-8")

    write_json(ROOT / "reports" / f"{source_event_key}-relay-member-import.json", relay_report)
    if compatibility:
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
    relay_markdown = "\n".join(relay_md) + "\n"
    (ROOT / "reports" / f"{source_event_key}-relay-member-import.md").write_text(relay_markdown, encoding="utf-8")
    if compatibility:
        (ROOT / "reports" / "relay-member-import-report.md").write_text(relay_markdown, encoding="utf-8")

    write_json(
        ROOT / "reports" / f"{source_event_key}-missing-data.json",
        {
            "event_id": source_event["event_id"],
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
    if compatibility:
        write_json(ROOT / "reports" / "eqtiming-missing-data.json", {
            "event_id": source_event["event_id"],
            "intermediate_splits_found": True,
            "available": "Official cumulative passages, split times, pace, speed and placings from EQ Timing's public contestant endpoint.",
            "known_limitations": [
                "DNS records and some DNF records have no or incomplete passages.",
                "Nolhaga is a timing point, not a relay exchange.",
                "A relay runner is attached to a leg only when separate start-list evidence verifies the mapping.",
            ],
            "rule": "No missing split, passing, leg time, or placing is interpolated or fabricated.",
        })


def _import_eqtiming_event(
    conn: sqlite3.Connection, config: dict[str, Any],
    catalog: dict[str, tuple[int, int | None, float | None]], source_event_key: str,
    source_event: dict[str, Any], bindings: dict[str, dict[str, Any]], compatibility: bool,
) -> dict[str, Any]:
    primary_results = source_event["primary_results"]
    primary_relay_legs = source_event.get("primary_relay_legs")
    primary_rows = load_primary_results(source_event)
    public_by_bib = _load_public_contestants(source_event)
    primary_by_race = bind_primary_results(primary_rows, source_event, bindings)

    assignments_by_race: dict[str, list[dict[str, Any]]] = {}
    patterns: dict[str, dict[str, Any]] = {}
    relay_bindings = {key: item for key, item in bindings.items() if isinstance(item["source_race"].get("relay"), dict)}
    xml_rows = load_xml_starts(source_event) if relay_bindings else []
    for race_key, resolved in relay_bindings.items():
        assignments, pattern = build_relay_assignments(
            race_key, primary_by_race[race_key], xml_rows, resolved["source_race"], source_event
        )
        if not pattern["verified"]:
            raise ValueError(f"Relay code pattern was not verified for {race_key}: {pattern}")
        assignments_by_race[race_key] = assignments
        patterns[race_key] = pattern

    cross_indexes, start_index = _cross_validation_indexes(source_event)
    source_ids = _insert_source_event(conn, source_event_key, source_event)
    web_races, report_races, result_ids, team_ids, web_splits = _insert_results(
        conn, config, catalog, primary_by_race, cross_indexes, start_index, public_by_bib,
        source_event, bindings, source_ids["official_resultlist"],
    )
    relay_report, web_teams, web_members, web_assignments = _insert_relay_data(
        conn, primary_by_race, assignments_by_race, patterns, result_ids, team_ids, source_event, bindings
    )
    split_coverage = _write_split_coverage(
        config, web_races, web_splits, source_event_key, source_event, bindings, compatibility
    )
    report = {
        "source_event_key": source_event_key, "provider": "eqtiming", "primary_result_source": primary_results,
        "primary_relay_leg_source": primary_relay_legs,
        "course_versions": sorted({item["race"]["course_version"] for item in bindings.values()}),
        "races": report_races,
        "limitations": [
            "CSV exports contain finish results only; official passages come from the cached public EQ Timing endpoint.",
            "Empty XML leg names are stored as missing and conflicts are never verified assignments.",
            "Missing passages are retained as missing and never interpolated.",
            "All original fields from CSV, XML and public JSON sources are preserved in raw_json.",
        ],
    }
    files_analysis = analyze_source_files(source_event, bindings)
    _write_reports(files_analysis, relay_report, report, source_event_key, source_event, compatibility)
    return {
        "web_races": web_races, "report_races": report_races, "web_splits": web_splits,
        "web_teams": web_teams, "web_members": web_members, "split_coverage": split_coverage,
        "relay_report": relay_report, "report": report,
    }


def import_all_official() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    groups = group_source_bindings(config)

    courses = resolve_all_courses(config, ROOT)
    for index, (course_key, course) in enumerate(courses.items()):
        definition = course["definition"]
        asset_dir = ROOT / "docs" / "data" / "courses" / course_key
        asset_dir.mkdir(parents=True, exist_ok=True)
        gpx_artifacts = build_gpx_artifacts(
            ROOT, course["route"], official_path=ROOT / definition["route_source"],
            reference_path=ROOT / definition["elevation_reference_source"] if definition.get("elevation_reference_source") else ROOT / "__missing_reference__",
            profile_path=asset_dir / "elevation.json", report_stem=f"gpx-comparison-{course_key}",
        )
        course["route"]["elevation_profile"] = gpx_artifacts["profile"]["meta"]
        course["route"]["route_master"] = "configured_gpx"
        course["elevation"] = gpx_artifacts["profile"]
        (asset_dir / "route.json").write_text(
            json.dumps(course["route"], ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
        )
        if index == 0:
            WEB_ROUTE.parent.mkdir(parents=True, exist_ok=True)
            WEB_ROUTE.write_text(json.dumps(course["route"], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            (ROOT / "docs/data/route-elevation-2026.json").write_text(
                json.dumps(gpx_artifacts["profile"], ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
            )
            for suffix in ("json", "md"):
                source = ROOT / "reports" / f"gpx-comparison-{course_key}.{suffix}"
                (ROOT / "reports" / f"gpx-comparison.{suffix}").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    conn = prepare_db()
    catalog, geometries = _insert_catalog(conn, config, courses)
    web_races: dict[str, Any] = {}
    report_races: dict[str, Any] = {}
    web_splits: list[dict[str, Any]] = []
    web_teams: list[dict[str, Any]] = []
    web_members: list[dict[str, Any]] = []
    split_coverage: dict[str, Any] = {}
    source_reports: dict[str, Any] = {}
    relay_reports: dict[str, Any] = {}
    source_summaries: dict[str, Any] = {}

    def import_group(group: dict[str, Any]) -> None:
        source_event_key = group["source_event_key"]
        source_event, bindings = eqtiming_source_context(config, source_event_key)
        imported = _import_eqtiming_event(
            conn, config, catalog, source_event_key, source_event, bindings, len(groups) == 1
        )
        web_races.update(imported["web_races"])
        report_races.update(imported["report_races"])
        web_splits.extend(imported["web_splits"])
        web_teams.extend(imported["web_teams"])
        web_members.extend(imported["web_members"])
        split_coverage.update(imported["split_coverage"]["races"])
        source_reports[source_event_key] = imported["report"]
        relay_reports[source_event_key] = imported["relay_report"]
        source_summaries[source_event_key] = {
            "provider": group["provider"], "event_id": source_event["event_id"],
            "results_url": source_event["results_url"], "race_editions": sorted(bindings),
        }

    dispatch_source_groups(config, {"eqtiming": import_group})

    conn.commit()
    conn.close()
    analyzable = set(web_races)
    web_payload = {
        "meta": {
            "project": "Gotaleden Splits", "event": config["event"], "source_events": source_summaries,
            "raw_fields_preserved": True, "intermediate_splits_available": True,
            "split_coverage": {
                key: {
                    "results_with_positive_passage": value["results_with_positive_passage"],
                    "complete_checkpoint_series": value["complete_checkpoint_series"],
                    "partial_checkpoint_series": value["partial_checkpoint_series"],
                }
                for key, value in split_coverage.items()
            },
        },
        "courses": web_course_catalog(courses),
        "race_catalog": web_race_catalog(config, analyzable),
        "checkpoints": {
            race["race_key"]: [
                {
                    "key": checkpoint["key"], "name": checkpoint["name"],
                    "nominal_cumulative_km": checkpoint["nominal_distance_km"],
                    "race_distance_km": checkpoint["nominal_distance_km"] - geometry["checkpoints"][0]["nominal_distance_km"],
                    "route_distance_km": checkpoint["route_distance_km"],
                    "route_distance_mapping": "piecewise_linear_explicit_anchors",
                    "is_timing_point": checkpoint.get("is_timing_point", True),
                    "is_relay_exchange": checkpoint.get("is_relay_exchange", False),
                    "timing_only": checkpoint.get("timing_only", False),
                    "analysis_boundary": checkpoint.get("analysis_boundary", True),
                    "replay_anchor": checkpoint.get("replay_anchor", True),
                    "speaker_checkpoint": checkpoint.get("speaker_checkpoint", False),
                    "segment_key_to_next": next((item["key"] for item in courses[race["course_version"]]["segments"] if item["from"] == checkpoint["key"]), None),
                    "segment_comparison_key_to_next": next((item.get("comparison_key") for item in courses[race["course_version"]]["segments"] if item["from"] == checkpoint["key"]), None),
                }
                for checkpoint in geometry["checkpoints"]
            ]
            for race in config["races"] if race["race_key"] in analyzable
            for geometry in (geometries[race["race_key"]],)
        },
        "races": web_races, "splits": web_splits, "teams": web_teams,
        "team_members": web_members,
    }
    write_payload(WEB_RESULTS, web_payload, WEB_RESULTS_COMPAT)
    report = {
        "event": config["event"],
        "course_versions": {
            key: {"fingerprint": course["fingerprint"], "point_count": course["route"]["point_count"],
                  "full_distance_km": course["route"]["full_distance_km"]}
            for key, course in courses.items()
        },
        "source_events": source_reports, "races": report_races,
        "limitations": [
            "Missing passages remain missing and are never interpolated.",
            "All original source fields are preserved in SQLite raw_json.",
        ],
    }
    write_payload(REPORT, report, REPORT_COMPAT, compact=False)
    print(json.dumps({
        "races": {key: value["record_count"] for key, value in report_races.items()},
        "source_events": sorted(source_reports), "relay": relay_reports,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import_all_official()
