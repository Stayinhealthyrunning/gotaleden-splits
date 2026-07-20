#!/usr/bin/env python3
"""Reproducible GPX comparison and reference-elevation projection.

The official GPX is always the route master. A personal Suunto export may add
elevation samples only after sequence-aware matching onto the official route.
"""
from __future__ import annotations

import json
import math
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

OFFICIAL_NAME = "Gotaleden_Ultra_75km-30april.gpx"
REFERENCE_NAME = "Suunto 9 baro Gotaleden 75.gpx"
PROFILE_RELATIVE_PATH = "docs/data/route-elevation-2026.json"


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radius = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def parse_gpx(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    namespace = root.tag.split("}")[0][1:] if root.tag.startswith("{") else ""
    prefix = f"{{{namespace}}}" if namespace else ""
    track_nodes = root.findall(f".//{prefix}trkpt")
    point_type = "trkpt" if track_nodes else "rtept"
    nodes = track_nodes or root.findall(f".//{prefix}rtept")
    points: list[dict[str, Any]] = []
    cumulative_m = 0.0
    previous: tuple[float, float] | None = None
    for node in nodes:
        lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
        coordinate = (lat, lon)
        step_m = haversine_m(previous, coordinate) if previous else 0.0
        cumulative_m += step_m
        elevation_node = node.find(f"{prefix}ele")
        time_node = node.find(f"{prefix}time")
        points.append({
            "lat": lat,
            "lon": lon,
            "elevation_m": float(elevation_node.text) if elevation_node is not None and elevation_node.text else None,
            "time": time_node.text if time_node is not None else None,
            "distance_km": cumulative_m / 1000,
            "step_m": step_m,
        })
        previous = coordinate
    if not points:
        raise ValueError(f"No track or route points in {path}")
    return {"path": path, "point_type": point_type, "points": points}


def _smoothed_elevations(values: list[float]) -> list[float]:
    result: list[float] = []
    for index in range(len(values)):
        window = values[max(0, index - 2) : min(len(values), index + 3)]
        result.append(statistics.median(window))
    return result


def _gain_loss(values: list[float]) -> tuple[float, float]:
    smoothed = _smoothed_elevations(values)
    ascent = descent = 0.0
    anchor = smoothed[0]
    for value in smoothed[1:]:
        difference = value - anchor
        if abs(difference) >= 1.0:
            if difference > 0:
                ascent += difference
            else:
                descent -= difference
            anchor = value
    return ascent, descent


def summarize(parsed: dict[str, Any]) -> dict[str, Any]:
    points = parsed["points"]
    elevations = [point["elevation_m"] for point in points if point["elevation_m"] is not None]
    times = [point["time"] for point in points if point["time"]]
    jumps = [
        {"from_index": index - 1, "to_index": index, "distance_m": round(point["step_m"], 1)}
        for index, point in enumerate(points)
        if point["step_m"] > 100
    ]
    ascent = descent = None
    if elevations:
        ascent, descent = _gain_loss(elevations)
    unique_elevation_steps = sorted({round(abs(b - a), 3) for a, b in zip(elevations, elevations[1:]) if b != a})
    return {
        "file": parsed["path"].name,
        "point_type": parsed["point_type"],
        "point_count": len(points),
        "first_coordinate": [round(points[0]["lat"], 8), round(points[0]["lon"], 8)],
        "last_coordinate": [round(points[-1]["lat"], 8), round(points[-1]["lon"], 8)],
        "track_distance_km": round(points[-1]["distance_km"], 4),
        "elevation_point_count": len(elevations),
        "elevation_coverage_pct": round(len(elevations) / len(points) * 100, 2),
        "min_elevation_m": round(min(elevations), 1) if elevations else None,
        "max_elevation_m": round(max(elevations), 1) if elevations else None,
        "ascent_m": round(ascent, 1) if ascent is not None else None,
        "descent_m": round(descent, 1) if descent is not None else None,
        "elevation_gain_loss_method": "5-point median followed by 1 m vertical deadband",
        "smallest_nonzero_elevation_step_m": unique_elevation_steps[0] if unique_elevation_steps else None,
        "timestamp_count": len(times),
        "timestamps_on_all_points": len(times) == len(points),
        "gps_jumps_over_100m": jumps,
    }


def _grid_key(lat: float, lon: float, size: float = 0.001) -> tuple[int, int]:
    return int(math.floor(lat / size)), int(math.floor(lon / size))


def _route_grid(points: list[dict[str, Any]]) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = {}
    for index, point in enumerate(points):
        grid.setdefault(_grid_key(point["lat"], point["lon"]), []).append(index)
    return grid


def _candidates(point: dict[str, Any], route: list[dict[str, Any]], grid: dict[tuple[int, int], list[int]]) -> list[tuple[float, int]]:
    key = _grid_key(point["lat"], point["lon"])
    indices: list[int] = []
    for radius in (1, 3, 8):
        indices = []
        for y in range(key[0] - radius, key[0] + radius + 1):
            for x in range(key[1] - radius, key[1] + radius + 1):
                indices.extend(grid.get((y, x), ()))
        if indices:
            break
    coordinate = (point["lat"], point["lon"])
    return sorted((haversine_m(coordinate, (route[i]["lat"], route[i]["lon"])), i) for i in indices)


def match_reference(official: dict[str, Any], reference: dict[str, Any]) -> list[dict[str, Any]]:
    route, ref = official["points"], reference["points"]
    grid = _route_grid(route)
    matches: list[dict[str, Any]] = []
    previous_route_index = 0
    for index, point in enumerate(ref):
        candidates = _candidates(point, route, grid)
        if not candidates:
            matches.append({"reference_index": index, "nearest_distance_m": None, "accepted": False})
            continue
        global_distance, global_index = candidates[0]
        previous_ref_km = ref[index - 1]["distance_km"] if index else 0.0
        expected_step_km = max(0.0, point["distance_km"] - previous_ref_km)
        max_forward_km = max(0.8, expected_step_km * 8 + 0.2)
        previous_km = route[previous_route_index]["distance_km"]
        sequential = [
            item for item in candidates
            if item[1] >= max(0, previous_route_index - 25)
            and route[item[1]]["distance_km"] <= previous_km + max_forward_km
        ]
        chosen_distance, chosen_index = sequential[0] if sequential else (global_distance, global_index)
        accepted = chosen_distance <= 50 and chosen_index >= previous_route_index - 25
        if accepted:
            previous_route_index = max(previous_route_index, chosen_index)
        matches.append({
            "reference_index": index,
            "reference_distance_km": point["distance_km"],
            "route_index": chosen_index,
            "route_distance_km": route[chosen_index]["distance_km"],
            "nearest_distance_m": global_distance,
            "sequential_distance_m": chosen_distance,
            "elevation_m": point["elevation_m"],
            "accepted": accepted,
        })
    return matches


def _off_route_sections(matches: list[dict[str, Any]], threshold_m: float) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    start: int | None = None
    for index, match in enumerate(matches + [{"nearest_distance_m": 0}]):
        off = match.get("nearest_distance_m") is None or match["nearest_distance_m"] > threshold_m
        if off and start is None:
            start = index
        elif not off and start is not None:
            end = index - 1
            if end - start + 1 >= 3:
                subset = matches[start : end + 1]
                sections.append({
                    "start_reference_index": start,
                    "end_reference_index": end,
                    "point_count": end - start + 1,
                    "start_reference_distance_km": round(subset[0]["reference_distance_km"], 3),
                    "end_reference_distance_km": round(subset[-1]["reference_distance_km"], 3),
                    "max_distance_from_official_m": round(max(item["nearest_distance_m"] or 0 for item in subset), 1),
                    "nearest_route_distance_km_at_start": round(subset[0].get("route_distance_km", 0), 3),
                    "nearest_route_distance_km_at_end": round(subset[-1].get("route_distance_km", 0), 3),
                })
            start = None
    return sections


def _interpolate_official(route: list[dict[str, Any]], distance_km: float) -> float | None:
    lo, hi = 0, len(route) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if route[mid]["distance_km"] < distance_km:
            lo = mid + 1
        else:
            hi = mid
    if route[lo]["elevation_m"] is not None:
        return route[lo]["elevation_m"]
    return None


def build_elevation_profile(official: dict[str, Any], reference: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    route = official["points"]
    full_km = route[-1]["distance_km"]
    matches = match_reference(official, reference) if reference else []
    valid = [item for item in matches if item.get("accepted") and item.get("elevation_m") is not None]
    coverage_km = 0.0
    if valid:
        covered_bins = {int(item["route_distance_km"] / 0.1) for item in valid}
        coverage_km = len(covered_bins) * 0.1
    use_reference = bool(reference and valid and coverage_km / full_km >= 0.7)
    vertical_adjustment = 0.0
    if use_reference:
        deltas = [
            route[item["route_index"]]["elevation_m"] - item["elevation_m"]
            for item in valid
            if route[item["route_index"]]["elevation_m"] is not None
        ]
        vertical_adjustment = statistics.median(deltas) if deltas else 0.0
    samples: list[dict[str, Any]] = []
    distance = 0.0
    while distance < full_km:
        nearby = [item for item in valid if abs(item["route_distance_km"] - distance) <= 0.075] if use_reference else []
        if nearby:
            elevation = statistics.median(item["elevation_m"] + vertical_adjustment for item in nearby)
            offset = statistics.median(item["sequential_distance_m"] for item in nearby)
            source = "suunto_reference_projected"
            confidence = "high" if offset <= 20 else "medium"
        else:
            elevation = _interpolate_official(route, distance)
            source = "official_gpx_fallback"
            confidence = "fallback"
        samples.append({"route_distance_km": round(distance, 4), "elevation_m": round(elevation, 1) if elevation is not None else None, "source": source, "confidence": confidence})
        distance += 0.05
    final_elevation = route[-1]["elevation_m"]
    nearby_final = [item for item in valid if abs(item["route_distance_km"] - full_km) <= 0.075] if use_reference else []
    if nearby_final:
        final_elevation = statistics.median(item["elevation_m"] + vertical_adjustment for item in nearby_final)
    samples.append({"route_distance_km": round(full_km, 4), "elevation_m": round(final_elevation, 1) if final_elevation is not None else None, "source": "suunto_reference_projected" if nearby_final else "official_gpx_fallback", "confidence": "high" if nearby_final else "fallback"})
    # Gentle three-sample smoothing; route distances and provenance remain unchanged.
    raw_values = [sample["elevation_m"] for sample in samples]
    for index, sample in enumerate(samples):
        window = [value for value in raw_values[max(0, index - 1) : min(len(samples), index + 2)] if value is not None]
        if window:
            sample["elevation_m"] = round(statistics.median(window), 1)
    values = [sample["elevation_m"] for sample in samples if sample["elevation_m"] is not None]
    ascent, descent = _gain_loss(values) if values else (None, None)
    metadata = {
        "route_master": OFFICIAL_NAME,
        "reference_file": REFERENCE_NAME if reference else None,
        "source": "official route with projected Suunto 9 Baro reference elevation" if use_reference else "official GPX elevation",
        "reference_used": use_reference,
        "reference_is_official": False,
        "vertical_datum_adjustment_m": round(vertical_adjustment, 2) if use_reference else None,
        "matching_threshold_m": 50,
        "reference_coverage_km": round(coverage_km, 2),
        "profile_spacing_km": 0.05,
        "smoothing": "three-sample median after 50 m aggregation",
        "ascent_m": round(ascent, 1) if ascent is not None else None,
        "descent_m": round(descent, 1) if descent is not None else None,
        "min_elevation_m": round(min(values), 1) if values else None,
        "max_elevation_m": round(max(values), 1) if values else None,
    }
    return {"meta": metadata, "points": samples}, {"matches": matches, "profile_meta": metadata}


def build_gpx_artifacts(root: Path, route_data: dict[str, Any] | None = None, reference_path: Path | None = None) -> dict[str, Any]:
    official_path = root / "data/source/gpx" / OFFICIAL_NAME
    reference_path = reference_path if reference_path is not None else root / "data/source/gpx" / REFERENCE_NAME
    official = parse_gpx(official_path)
    reference = parse_gpx(reference_path) if reference_path.exists() else None
    profile, detail = build_elevation_profile(official, reference)
    official_summary = summarize(official)
    reference_summary = summarize(reference) if reference else None
    matches = detail["matches"]
    start_distance = haversine_m(
        (official["points"][0]["lat"], official["points"][0]["lon"]),
        (reference["points"][0]["lat"], reference["points"][0]["lon"]),
    ) if reference else None
    finish_distance = haversine_m(
        (official["points"][-1]["lat"], official["points"][-1]["lon"]),
        (reference["points"][-1]["lat"], reference["points"][-1]["lon"]),
    ) if reference else None
    route_verification = None
    if route_data and route_data.get("points"):
        route_start = route_data["points"][0]
        route_finish = route_data["points"][-1]
        route_verification = {
            "point_count": route_data["point_count"],
            "first_coordinate": route_start[:2],
            "last_coordinate": route_finish[:2],
            "full_distance_km": route_data["full_distance_km"],
            "start_distance_from_official_m": round(haversine_m((official["points"][0]["lat"], official["points"][0]["lon"]), (route_start[0], route_start[1])), 2),
            "finish_distance_from_official_m": round(haversine_m((official["points"][-1]["lat"], official["points"][-1]["lon"]), (route_finish[0], route_finish[1])), 2),
        }
    report = {
        "route_master": {"file": OFFICIAL_NAME, "role": "official geometry, distance, checkpoint projection and replay"},
        "personal_reference": {"file": REFERENCE_NAME, "device": "Suunto 9 Baro", "official": False, "role": "start/finish verification, elevation reference and quality control", "known_geometry_issue": "The runner is known to have left the official route at least once; reference geometry never replaces the master route."},
        "official": official_summary,
        "suunto_reference": reference_summary,
        "generated_route_data_verification": route_verification,
        "start_distance_between_files_m": round(start_distance, 1) if start_distance is not None else None,
        "finish_distance_between_files_m": round(finish_distance, 1) if finish_distance is not None else None,
        "off_route_sections_over_50m": _off_route_sections(matches, 50) if matches else [],
        "off_route_sections_over_100m": _off_route_sections(matches, 100) if matches else [],
        "matching": {
            "method": "global spatial nearest candidates with sequence-aware monotonic route window",
            "accepted_threshold_m": 50,
            "matched_points": sum(1 for item in matches if item.get("accepted")),
            "reference_points": len(matches),
            "median_nearest_distance_m": round(statistics.median(item["nearest_distance_m"] for item in matches if item.get("nearest_distance_m") is not None), 1) if matches else None,
            "max_nearest_distance_m": round(max(item["nearest_distance_m"] for item in matches if item.get("nearest_distance_m") is not None), 1) if matches else None,
        },
        "elevation_profile": profile["meta"],
    }
    report_dir = root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "gpx-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# GPX comparison", "",
        "The official GPX remains the sole route master. The Suunto 9 Baro file is a personal reference measurement and never replaces route geometry.", "",
        "| Metric | Official GPX | Suunto reference |", "|---|---:|---:|",
        f"| Point type | {official_summary['point_type']} | {reference_summary['point_type'] if reference_summary else 'missing'} |",
        f"| Points | {official_summary['point_count']} | {reference_summary['point_count'] if reference_summary else 'missing'} |",
        f"| Distance | {official_summary['track_distance_km']:.4f} km | {reference_summary['track_distance_km'] if reference_summary else 'missing'} km |",
        f"| Elevation min/max | {official_summary['min_elevation_m']} / {official_summary['max_elevation_m']} m | {reference_summary['min_elevation_m'] if reference_summary else 'missing'} / {reference_summary['max_elevation_m'] if reference_summary else 'missing'} m |",
        f"| Ascent/descent | {official_summary['ascent_m']} / {official_summary['descent_m']} m | {reference_summary['ascent_m'] if reference_summary else 'missing'} / {reference_summary['descent_m'] if reference_summary else 'missing'} m |", "",
        f"Start separation: **{report['start_distance_between_files_m']} m**. Finish separation: **{report['finish_distance_between_files_m']} m**.", "",
        f"Suunto timestamps: **{reference_summary['timestamp_count'] if reference_summary else 0}**. Elevation coverage: **{reference_summary['elevation_coverage_pct'] if reference_summary else 0}%**.", "",
        f"Sequence-aware matching accepted {report['matching']['matched_points']} of {report['matching']['reference_points']} reference points. Median nearest offset: {report['matching']['median_nearest_distance_m']} m.", "",
        f"Contiguous off-route sections: **{len(report['off_route_sections_over_50m'])} over 50 m**, **{len(report['off_route_sections_over_100m'])} over 100 m**. These are observations, not automatic labels of the known wrong turn.", "",
        f"Elevation profile source: **{profile['meta']['source']}**. Vertical alignment applied: {profile['meta']['vertical_datum_adjustment_m']} m. Reference coverage: {profile['meta']['reference_coverage_km']} km.", "",
        "See `gpx-comparison.json` for section boundaries and exact metrics.",
    ]
    (report_dir / "gpx-comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    profile_path = root / PROFILE_RELATIVE_PATH
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"report": report, "profile": profile}


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    result = build_gpx_artifacts(project_root)
    print(json.dumps({"official": result["report"]["official"], "suunto": result["report"]["suunto_reference"], "profile": result["profile"]["meta"]}, ensure_ascii=False, indent=2))
