"""Provider-neutral CourseVersion resolution and comparability contracts."""
from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class CourseConfigError(ValueError):
    pass


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radius = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def course_definitions(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    courses = config.get("course_versions")
    catalogs = config.get("checkpoint_catalogs")
    if not isinstance(courses, dict) or not courses:
        raise CourseConfigError("course_versions must be a non-empty object")
    if not isinstance(catalogs, dict) or not catalogs:
        raise CourseConfigError("checkpoint_catalogs must be a non-empty object")
    for key, course in courses.items():
        if not isinstance(course, dict):
            raise CourseConfigError(f"CourseVersion {key!r} must be an object")
        missing = [name for name in ("event_key", "route_source", "checkpoint_catalog", "anchors", "segments") if course.get(name) in (None, "")]
        if missing:
            raise CourseConfigError(f"CourseVersion {key!r} is missing: {', '.join(missing)}")
        if course["checkpoint_catalog"] not in catalogs:
            raise CourseConfigError(f"CourseVersion {key!r} references unknown checkpoint catalog {course['checkpoint_catalog']!r}")
    return courses


def checkpoint_catalog(config: dict[str, Any], course: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = config["checkpoint_catalogs"][course["checkpoint_catalog"]]
    if not isinstance(catalog, list) or len(catalog) < 2:
        raise CourseConfigError(f"Checkpoint catalog {course['checkpoint_catalog']!r} must contain at least two checkpoints")
    keys = [item.get("key") for item in catalog if isinstance(item, dict)]
    if len(keys) != len(catalog) or any(not key for key in keys) or len(set(keys)) != len(keys):
        raise CourseConfigError(f"Checkpoint catalog {course['checkpoint_catalog']!r} has invalid or duplicate keys")
    return catalog


def _route_points(path: Path) -> list[list[float | None]]:
    root = ET.parse(path).getroot()
    namespace = root.tag.split("}")[0][1:] if root.tag.startswith("{") else ""
    prefix = f"{{{namespace}}}" if namespace else ""
    nodes = root.findall(f".//{prefix}trkpt") or root.findall(f".//{prefix}rtept")
    if not nodes:
        raise CourseConfigError(f"No route points in {path}")
    points: list[list[float | None]] = []
    cumulative_m = 0.0
    previous: tuple[float, float] | None = None
    for node in nodes:
        lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
        if previous is not None:
            cumulative_m += haversine_m(previous, (lat, lon))
        elevation_node = node.find(f"{prefix}ele")
        elevation = float(elevation_node.text) if elevation_node is not None and elevation_node.text else None
        points.append([round(lat, 6), round(lon, 6), None if elevation is None else round(elevation, 1), round(cumulative_m / 1000, 4)])
        previous = (lat, lon)
    return points


def _gpx_geometry_digest(raw: bytes) -> str:
    root = ET.fromstring(raw)
    namespace = root.tag.split("}")[0][1:] if root.tag.startswith("{") else ""
    prefix = f"{{{namespace}}}" if namespace else ""
    nodes = root.findall(f".//{prefix}trkpt") or root.findall(f".//{prefix}rtept")
    if not nodes:
        raise CourseConfigError("No route points in GPX source")
    material = {
        "format": "gpx-geometry-v1",
        "points": [
            [
                float(node.attrib["lat"]),
                float(node.attrib["lon"]),
                None if (elevation := node.find(f"{prefix}ele")) is None or not elevation.text else float(elevation.text),
            ]
            for node in nodes
        ],
    }
    payload = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_material_digest(path: Path) -> str:
    """Hash semantic GPX geometry, falling back to newline-normalized text."""
    raw = path.read_bytes()
    if path.suffix.casefold() == ".gpx":
        return _gpx_geometry_digest(raw)
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _material_definition(root: Path, key: str, course: dict[str, Any], checkpoints: list[dict[str, Any]], source_digests: dict[str, str | None] | None = None) -> dict[str, Any]:
    source_fields = {}
    for field in ("route_source", "elevation_reference_source"):
        relative = course.get(field)
        source_fields[field] = source_digests[field] if source_digests is not None else None if not relative else _source_material_digest(root / relative)
    return {
        "key": key,
        "event_key": course["event_key"],
        "sources": source_fields,
        "checkpoints": checkpoints,
        "anchors": course["anchors"],
        "segments": course["segments"],
        "whole_course_comparison_group": course.get("whole_course_comparison_group"),
    }


def course_fingerprint(root: Path, key: str, course: dict[str, Any], checkpoints: list[dict[str, Any]]) -> str:
    return _fingerprint_material(_material_definition(root, key, course, checkpoints))


def _fingerprint_material(material: dict[str, Any]) -> str:
    payload = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_anchors(course: dict[str, Any], checkpoints: list[dict[str, Any]], points: list[list[float | None]]) -> list[dict[str, Any]]:
    checkpoint_map = {item["key"]: item for item in checkpoints}
    resolved = []
    for anchor in course["anchors"]:
        if not isinstance(anchor, dict) or not anchor.get("key"):
            raise CourseConfigError("Every route anchor must have a key")
        checkpoint = checkpoint_map.get(anchor.get("checkpoint"))
        nominal = anchor.get("nominal_distance_km", checkpoint.get("nominal_distance_km") if checkpoint else None)
        if nominal is None:
            raise CourseConfigError(f"Anchor {anchor['key']!r} has no nominal distance")
        if anchor.get("route_position") == "start":
            route_index, route_distance, snap_distance = 0, 0.0, 0.0
        elif anchor.get("route_position") == "end":
            route_index, route_distance, snap_distance = len(points) - 1, float(points[-1][3]), 0.0
        elif isinstance(anchor.get("route_distance_km"), (int, float)):
            route_distance = float(anchor["route_distance_km"])
            route_index = min(range(len(points)), key=lambda index: abs(float(points[index][3]) - route_distance))
            snap_distance = 0.0
        elif isinstance(anchor.get("coordinate"), dict):
            coordinate = anchor["coordinate"]
            target = (float(coordinate["lat"]), float(coordinate["lon"]))
            route_index = min(range(len(points)), key=lambda index: haversine_m(target, (float(points[index][0]), float(points[index][1]))))
            snap_distance = haversine_m(target, (float(points[route_index][0]), float(points[route_index][1])))
            maximum = float(anchor.get("max_snap_distance_m", 100))
            if snap_distance > maximum:
                raise CourseConfigError(f"Anchor {anchor['key']!r} is {snap_distance:.2f} m from route (maximum {maximum:.2f} m)")
            route_distance = float(points[route_index][3])
        else:
            raise CourseConfigError(f"Anchor {anchor['key']!r} has no route position, distance or coordinate")
        resolved.append({
            "key": anchor["key"], "checkpoint": anchor.get("checkpoint"),
            "nominal_distance_km": float(nominal), "route_distance_km": round(route_distance, 4),
            "route_index": route_index, "snap_distance_m": round(snap_distance, 2),
        })
    resolved.sort(key=lambda item: item["nominal_distance_km"])
    if len(resolved) < 2:
        raise CourseConfigError("A CourseVersion needs at least two route anchors")
    for previous, current in zip(resolved, resolved[1:]):
        if current["nominal_distance_km"] <= previous["nominal_distance_km"] or current["route_distance_km"] <= previous["route_distance_km"]:
            raise CourseConfigError("CourseVersion anchors must be strictly monotonic in nominal and route distance")
    return resolved


def map_nominal_distance(nominal_distance_km: float, anchors: list[dict[str, Any]]) -> float:
    nominal = float(nominal_distance_km)
    if nominal < anchors[0]["nominal_distance_km"] or nominal > anchors[-1]["nominal_distance_km"]:
        raise CourseConfigError(f"Nominal distance {nominal} is outside the declared anchor range")
    for anchor in anchors:
        if nominal == anchor["nominal_distance_km"]:
            return float(anchor["route_distance_km"])
    for left, right in zip(anchors, anchors[1:]):
        if left["nominal_distance_km"] < nominal < right["nominal_distance_km"]:
            share = (nominal - left["nominal_distance_km"]) / (right["nominal_distance_km"] - left["nominal_distance_km"])
            return round(left["route_distance_km"] + share * (right["route_distance_km"] - left["route_distance_km"]), 4)
    raise CourseConfigError(f"Could not map nominal distance {nominal}")


def resolve_course_version(config: dict[str, Any], root: Path, key: str) -> dict[str, Any]:
    courses = course_definitions(config)
    course = courses.get(key)
    if course is None:
        raise CourseConfigError(f"Unknown CourseVersion {key!r}")
    checkpoints = checkpoint_catalog(config, course)
    points = _route_points(root / course["route_source"])
    anchors = _resolve_anchors(course, checkpoints, points)
    fingerprint = course_fingerprint(root, key, course, checkpoints)
    expected = course.get("expected_fingerprint")
    if expected and expected != "PENDING" and expected != fingerprint:
        raise CourseConfigError(f"Immutable CourseVersion {key!r} fingerprint changed: expected {expected}, got {fingerprint}; create a new version id")
    checkpoint_values = []
    for checkpoint in checkpoints:
        nominal = float(checkpoint["nominal_distance_km"])
        checkpoint_values.append({**checkpoint, "route_distance_km": map_nominal_distance(nominal, anchors)})
    checkpoint_map = {item["key"]: item for item in checkpoint_values}
    segment_values = []
    for segment in course["segments"]:
        start, end = checkpoint_map.get(segment.get("from")), checkpoint_map.get(segment.get("to"))
        if not start or not end or end["route_distance_km"] <= start["route_distance_km"]:
            raise CourseConfigError(f"CourseVersion {key!r} has invalid segment {segment!r}")
        segment_values.append({**segment, "course_version": key})
    return {
        "key": key, "event_key": course["event_key"], "fingerprint": fingerprint,
        "whole_course_comparison_group": course.get("whole_course_comparison_group"),
        "route": {
            "source": course["route_source"], "course_version": key, "fingerprint": fingerprint,
            "point_count": len(points), "full_distance_km": float(points[-1][3]), "anchors": anchors,
            "official_elevation_gain_m": course.get("official_elevation_gain_m"),
            "official_elevation_loss_m": course.get("official_elevation_loss_m"), "points": points,
        },
        "checkpoints": checkpoint_values, "segments": segment_values, "definition": course,
    }


def resolve_all_courses(config: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    return {key: resolve_course_version(config, root, key) for key in course_definitions(config)}


def race_course_geometry(race: dict[str, Any], course: dict[str, Any]) -> dict[str, Any]:
    if race.get("course_version") != course["key"]:
        raise CourseConfigError(f"Race {race.get('race_key')!r} does not reference CourseVersion {course['key']!r}")
    checkpoint_map = {item["key"]: item for item in course["checkpoints"]}
    route_range = race.get("route_range")
    if not isinstance(route_range, dict) or route_range.get("from") not in checkpoint_map or route_range.get("to") not in checkpoint_map:
        raise CourseConfigError(f"Race {race.get('race_key')!r} has an invalid route_range")
    start = checkpoint_map[route_range["from"]]
    end = checkpoint_map[route_range["to"]]
    if end["route_distance_km"] <= start["route_distance_km"]:
        raise CourseConfigError(f"Race {race.get('race_key')!r} route_range is not monotonic")
    keys = race.get("checkpoint_keys")
    if not isinstance(keys, list) or len(keys) < 2 or keys[0] != start["key"] or keys[-1] != end["key"]:
        raise CourseConfigError(f"Race {race.get('race_key')!r} checkpoint_keys must span route_range")
    checkpoints = [checkpoint_map[key] for key in keys]
    if any(right["route_distance_km"] <= left["route_distance_km"] for left, right in zip(checkpoints, checkpoints[1:])):
        raise CourseConfigError(f"Race {race.get('race_key')!r} checkpoints are not monotonic")
    return {
        "start_route_distance_km": start["route_distance_km"], "end_route_distance_km": end["route_distance_km"],
        "gpx_distance_km": round(end["route_distance_km"] - start["route_distance_km"], 4), "checkpoints": checkpoints,
    }


def course_comparability(race_a: dict[str, Any], race_b: dict[str, Any], courses: dict[str, dict[str, Any]]) -> str:
    if race_a.get("race_family") != race_b.get("race_family"):
        return "incomparable"
    key_a, key_b = race_a.get("course_version"), race_b.get("course_version")
    if key_a == key_b and key_a in courses:
        return "exact"
    group_a = courses.get(key_a, {}).get("whole_course_comparison_group")
    group_b = courses.get(key_b, {}).get("whole_course_comparison_group")
    return "compatible" if group_a and group_a == group_b else "incomparable"


def segment_comparability(segment_a: dict[str, Any], segment_b: dict[str, Any]) -> str:
    if segment_a.get("course_version") == segment_b.get("course_version") and segment_a.get("key") == segment_b.get("key"):
        return "exact"
    comparison_a, comparison_b = segment_a.get("comparison_key"), segment_b.get("comparison_key")
    return "compatible" if comparison_a and comparison_a == comparison_b else "incomparable"


def web_course_catalog(courses: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": key, "event_key": course["event_key"], "fingerprint": course["fingerprint"],
            "whole_course_comparison_group": course.get("whole_course_comparison_group"),
            "assets": {"route": f"data/courses/{key}/route.json", "elevation": f"data/courses/{key}/elevation.json"},
            "segments": course["segments"],
        }
        for key, course in courses.items()
    }
