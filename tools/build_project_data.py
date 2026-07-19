#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "races.json"
DB = ROOT / "data" / "gotaleden.sqlite"
WEB_RESULTS = ROOT / "docs" / "data" / "results-2026.json"
WEB_ROUTE = ROOT / "docs" / "data" / "route.json"
REPORT = ROOT / "reports" / "import-summary-2026.json"

def normalize(value: str | None) -> str:
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def to_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None

def to_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None

def clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None

def status_code(value: str | None) -> str:
    v = (value or "").strip().upper()
    return {
        "TIME": "FINISHED",
        "FINISHED": "FINISHED",
        "DNF": "DNF",
        "DNS": "DNS",
        "DSQ": "DSQ",
    }.get(v, v or "UNKNOWN")

def haversine_m(a, b) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(x))

def load_route(config):
    gpx_path = ROOT / config["route"]["source_gpx"]
    root = ET.parse(gpx_path).getroot()
    ns = {}
    if root.tag.startswith("{"):
        ns = {"g": root.tag.split("}")[0][1:]}
        trkpts = root.findall(".//g:trkpt", ns)
    else:
        trkpts = root.findall(".//trkpt")

    pts = []
    cumulative = 0.0
    previous = None
    for node in trkpts:
        lat = float(node.attrib["lat"])
        lon = float(node.attrib["lon"])
        ele_node = node.find("g:ele", ns) if ns else node.find("ele")
        ele = float(ele_node.text) if ele_node is not None and ele_node.text else None
        if previous is not None:
            cumulative += haversine_m(previous, (lat, lon))
        pts.append([round(lat, 6), round(lon, 6), None if ele is None else round(ele, 1), round(cumulative / 1000, 4)])
        previous = (lat, lon)

    floda = config["route"]["floda_start"]
    target = (floda["lat"], floda["lon"])
    nearest_index = min(
        range(len(pts)),
        key=lambda i: haversine_m(target, (pts[i][0], pts[i][1]))
    )
    nearest_distance_m = haversine_m(target, (pts[nearest_index][0], pts[nearest_index][1]))
    full_km = pts[-1][3]
    distance_35_km = round(full_km - pts[nearest_index][3], 4)

    return {
        "source": config["route"]["source_gpx"],
        "point_count": len(pts),
        "full_distance_km": full_km,
        "floda_start": {
            "requested": target,
            "route_point": [pts[nearest_index][0], pts[nearest_index][1]],
            "route_index": nearest_index,
            "distance_from_requested_m": round(nearest_distance_m, 2),
            "cumulative_km_from_gothenburg": pts[nearest_index][3],
            "remaining_distance_km": distance_35_km,
        },
        "official_elevation_gain_m": config["route"]["official_elevation_gain_m"],
        "official_elevation_loss_m": config["route"]["official_elevation_loss_m"],
        "points": pts,
    }

def prepare_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT / "tools" / "schema.sql").read_text(encoding="utf-8"))
    return conn

def import_all():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    route = load_route(config)
    WEB_ROUTE.parent.mkdir(parents=True, exist_ok=True)
    WEB_ROUTE.write_text(json.dumps(route, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    conn = prepare_db()
    with conn:
        conn.execute(
            "INSERT INTO sources(code,name,base_url,source_type) VALUES(?,?,?,?)",
            ("eqtiming_csv", "EQ Timing resultat-/pressfil", "https://live.eqtiming.com/77906", "csv")
        )
    source_id = conn.execute("SELECT id FROM sources WHERE code='eqtiming_csv'").fetchone()[0]

    checkpoint_catalog = {cp["key"]: cp for cp in config["checkpoints"]}
    web_races = {}
    report = {
        "event": config["event"],
        "route": {
            "point_count": route["point_count"],
            "full_distance_km": route["full_distance_km"],
            "floda_start": route["floda_start"],
        },
        "races": {},
        "limitations": [
            "Startfilerna innehåller endast PointName=Mål; mellanpassager finns inte som separata CSV-rader.",
            "Stafettfilerna innehåller lagnamn och ett listat personnamn, men ingen verifierad komplett koppling mellan lagmedlem och etapp.",
            "Alla 81 originalkolumner bevaras i raw-fältet och i SQLite raw_json."
        ]
    }

    for race in config["races"]:
        gpx_distance = route["full_distance_km"] if race["route_start"] == "gothenburg" else route["floda_start"]["remaining_distance_km"]
        with conn:
            conn.execute(
                """INSERT INTO races(race_key,section_name,source_race_name,race_type,year,race_date,
                   nominal_distance_km,gpx_distance_km,official_url)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    race["race_key"], race["section"], race["source_race_name"], race["type"],
                    config["event"]["year"], config["event"]["date"], race["nominal_distance_km"],
                    gpx_distance, config["event"]["official_results_url"]
                )
            )
        race_id = conn.execute("SELECT id FROM races WHERE race_key=?", (race["race_key"],)).fetchone()[0]

        for seq, key in enumerate(race["checkpoints"]):
            cp = checkpoint_catalog[key]
            if race["route_start"] == "floda":
                base = checkpoint_catalog["floda"]["nominal_cumulative_km_75"]
                nominal = cp["nominal_cumulative_km_75"] - base
            else:
                nominal = cp["nominal_cumulative_km_75"]
            with conn:
                conn.execute(
                    "INSERT INTO checkpoints(race_id,checkpoint_key,name,sequence_no,nominal_distance_km) VALUES(?,?,?,?,?)",
                    (race_id, key, cp["name"], seq, nominal)
                )

        finish_key = race["checkpoints"][-1]
        finish_cp_id = conn.execute(
            "SELECT id FROM checkpoints WHERE race_id=? AND checkpoint_key=?", (race_id, finish_key)
        ).fetchone()[0]

        csv_path = ROOT / race["source_csv"]
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            original_columns = reader.fieldnames or []

        normalized_rows = []
        status_counts = {}
        class_counts = {}

        for row in rows:
            raw = {k: (v if v != "" else None) for k, v in row.items()}
            bib = clean(row.get("Bib"))
            published_name = clean(row.get("NameFormatted")) or "Okänd"
            listed_contact = " ".join(x for x in [clean(row.get("Firstname")), clean(row.get("Surname"))] if x) or None
            status = status_code(row.get("Status"))
            status_counts[status] = status_counts.get(status, 0) + 1
            class_name = clean(row.get("ClassName"))
            if class_name:
                class_counts[class_name.strip()] = class_counts.get(class_name.strip(), 0) + 1

            finish_ms = to_int(row.get("AccumulatedTime")) if status == "FINISHED" else None
            finish_seconds = (finish_ms / 1000.0) if finish_ms is not None else None

            athlete_id = None
            team_id = None
            entity_type = "athlete" if race["type"] == "individual" else "team"

            if entity_type == "athlete":
                with conn:
                    conn.execute(
                        "INSERT INTO athletes(canonical_name,normalized_name,sex,nationality) VALUES(?,?,?,?)",
                        (published_name, normalize(published_name), clean(row.get("Gender")), clean(row.get("Nation")))
                    )
                athlete_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                with conn:
                    conn.execute(
                        "INSERT INTO teams(team_name,normalized_name,class_name,listed_contact_name) VALUES(?,?,?,?)",
                        (published_name, normalize(published_name), class_name, listed_contact)
                    )
                team_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            source_result_id = bib or f"row-{len(normalized_rows)+1}"
            with conn:
                conn.execute(
                    """INSERT INTO results(
                       race_id,source_id,source_result_id,entity_type,athlete_id,team_id,bib,name_as_published,
                       listed_contact_name,sex,class_name,nationality,club,status,finish_seconds,finish_milliseconds,
                       overall_place,gender_place,class_place,start_time,passing_time,role_km,raw_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        race_id, source_id, source_result_id, entity_type, athlete_id, team_id, bib, published_name,
                        listed_contact if entity_type == "team" else None,
                        clean(row.get("Gender")), class_name, clean(row.get("Nation")), clean(row.get("Club")),
                        status, finish_seconds, finish_ms, to_int(row.get("RankTotal")), to_int(row.get("RankGender")),
                        to_int(row.get("RankClass")), clean(row.get("Starttime")), clean(row.get("PassingTime")),
                        to_float(row.get("RoleKm")), json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
                    )
                )
            result_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # The source files are finish exports. Store the finish passage exactly as provided,
            # but do not invent intermediate splits.
            if finish_seconds is not None:
                with conn:
                    conn.execute(
                        """INSERT INTO splits(result_id,checkpoint_id,elapsed_seconds,place_overall,place_gender,
                           place_class,source_point_name,is_finish_only_export,raw_json)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (
                            result_id, finish_cp_id, finish_seconds, to_int(row.get("RankTotal")),
                            to_int(row.get("RankGender")), to_int(row.get("RankClass")),
                            clean(row.get("PointName")), 1,
                            json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
                        )
                    )

            normalized_rows.append({
                "source_result_id": source_result_id,
                "bib": bib,
                "entity_type": entity_type,
                "name": published_name,
                "listed_contact_name": listed_contact if entity_type == "team" else None,
                "sex": clean(row.get("Gender")),
                "class_name": class_name,
                "nation": clean(row.get("Nation")),
                "club": clean(row.get("Club")),
                "status": status,
                "finish_seconds": finish_seconds,
                "finish_time_formatted": clean(row.get("TimeFormatted")),
                "overall_place": to_int(row.get("RankTotal")),
                "gender_place": to_int(row.get("RankGender")),
                "class_place": to_int(row.get("RankClass")),
                "start_time": clean(row.get("Starttime")),
                "passing_time": clean(row.get("PassingTime")),
                "role_km": to_float(row.get("RoleKm")),
                "finish_point_only": True,
                "raw": raw,
            })

        web_races[race["race_key"]] = {
            "race_key": race["race_key"],
            "section": race["section"],
            "source_race_name": race["source_race_name"],
            "type": race["type"],
            "nominal_distance_km": race["nominal_distance_km"],
            "gpx_distance_km": gpx_distance,
            "records": normalized_rows,
        }
        report["races"][race["race_key"]] = {
            "section": race["section"],
            "source_race_name": race["source_race_name"],
            "record_count": len(normalized_rows),
            "original_column_count": len(original_columns),
            "original_columns": original_columns,
            "statuses": status_counts,
            "classes": class_counts,
            "point_names": sorted({clean(r.get("PointName")) for r in rows if clean(r.get("PointName"))}),
            "role_km_values": sorted({to_float(r.get("RoleKm")) for r in rows if to_float(r.get("RoleKm")) is not None}),
            "intermediate_split_rows_in_csv": sum(1 for r in rows if clean(r.get("PointName")) not in {None, "Mål"}),
        }

    conn.commit()
    conn.close()

    web_payload = {
        "meta": {
            "project": "Gotaleden Splits",
            "event": config["event"],
            "data_source": "EQ Timing CSV export",
            "raw_fields_preserved": True,
            "intermediate_splits_available_in_current_csv": False,
        },
        "races": web_races,
    }
    WEB_RESULTS.write_text(json.dumps(web_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    from build_official_data import import_all_official

    import_all_official()
