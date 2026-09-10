"""Provider-neutral race catalog and source-binding resolution."""
from __future__ import annotations

from typing import Any, Callable


class SourceBindingError(ValueError):
    pass


DATA_STATUSES = frozenset({"available", "planned"})
PARTICIPANT_ENTITIES = frozenset({"person", "team"})
TEAM_STRUCTURES = frozenset({"none", "sequential"})
MEMBER_ASSIGNMENTS = frozenset({"unknown", "explicit"})
CAPABILITIES = frozenset({
    "goal_pace", "sex_filter", "age_analysis", "club_analysis", "person_history",
    "team_members", "class_analysis", "segment_analysis", "replay", "head_to_head",
})


def event_contract(config: dict[str, Any]) -> dict[str, Any]:
    event = config.get("event")
    if not isinstance(event, dict):
        raise SourceBindingError("event must be an object")
    missing = [key for key in ("event_key", "name", "product_title", "official_site_url", "storage_namespace") if not event.get(key)]
    if missing:
        raise SourceBindingError(f"Event is missing presentation fields: {', '.join(missing)}")
    profiles = config.get("competition_profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SourceBindingError("competition_profiles must be a non-empty object")
    schemes = config.get("class_schemes", {})
    if not isinstance(schemes, dict):
        raise SourceBindingError("class_schemes must be an object")
    for scheme_key, scheme in schemes.items():
        classes = scheme.get("classes") if isinstance(scheme, dict) else None
        if not isinstance(classes, list):
            raise SourceBindingError(f"Class scheme {scheme_key!r} must contain classes")
        ids = [item.get("id") for item in classes if isinstance(item, dict)]
        names = [item.get("source_name") for item in classes if isinstance(item, dict)]
        if len(ids) != len(classes) or any(not value for value in ids + names) or len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise SourceBindingError(f"Class scheme {scheme_key!r} has missing or duplicate ids/source names")
    return event


def race_contract(config: dict[str, Any], race: dict[str, Any]) -> dict[str, Any]:
    event_contract(config)
    race_key = race.get("race_key") or "<missing>"
    profile_key = race.get("competition_profile")
    profile = config["competition_profiles"].get(profile_key)
    if not isinstance(profile, dict):
        raise SourceBindingError(f"Race {race_key} references unknown competition_profile {profile_key!r}")
    participant = profile.get("participant")
    competition = profile.get("competition")
    capabilities = profile.get("capabilities")
    ui_labels = profile.get("ui_labels", {})
    if not isinstance(participant, dict) or participant.get("entity") not in PARTICIPANT_ENTITIES:
        raise SourceBindingError(f"Race {race_key} has invalid participant entity")
    if any(not participant.get(key) for key in ("singular", "plural", "profile_label", "possessive")):
        raise SourceBindingError(f"Race {race_key} has incomplete participant labels")
    if not isinstance(competition, dict) or not isinstance(competition.get("format"), str) or not competition["format"]:
        raise SourceBindingError(f"Race {race_key} has invalid competition format")
    structure = {**(competition.get("team_structure") or {}), **(race.get("team_structure") or {})}
    if structure.get("kind") not in TEAM_STRUCTURES or structure.get("member_assignment") not in MEMBER_ASSIGNMENTS:
        raise SourceBindingError(f"Race {race_key} has invalid team structure")
    if structure["kind"] == "sequential" and (not isinstance(structure.get("leg_count"), int) or structure["leg_count"] <= 0):
        raise SourceBindingError(f"Race {race_key} sequential team structure requires a positive leg_count")
    if participant["entity"] == "person" and structure["kind"] != "none":
        raise SourceBindingError(f"Race {race_key} person entity cannot have team legs")
    if not isinstance(capabilities, dict) or set(capabilities) - CAPABILITIES or any(not isinstance(value, bool) for value in capabilities.values()):
        raise SourceBindingError(f"Race {race_key} has invalid capabilities")
    if not isinstance(ui_labels, dict) or any(not isinstance(value, str) or not value.strip() for value in ui_labels.values()):
        raise SourceBindingError(f"Race {race_key} has invalid UI labels")
    presentation = race.get("presentation")
    if not isinstance(presentation, dict) or not presentation.get("distance_label") or not isinstance(presentation.get("route_stops"), list) or len(presentation["route_stops"]) < 2:
        raise SourceBindingError(f"Race {race_key} has incomplete presentation metadata")
    scheme_key = race.get("class_scheme")
    if scheme_key and scheme_key not in config.get("class_schemes", {}):
        raise SourceBindingError(f"Race {race_key} references unknown class_scheme {scheme_key!r}")
    goal_pace = race.get("goal_pace")
    if capabilities.get("goal_pace"):
        values = [goal_pace.get(key) if isinstance(goal_pace, dict) else None for key in ("minimum_seconds", "maximum_seconds", "default_seconds")]
        if any(not isinstance(value, int) or value <= 0 for value in values) or not values[0] <= values[2] <= values[1]:
            raise SourceBindingError(f"Race {race_key} with goal pace requires valid target bounds/default")
    return {
        "participant": participant,
        "ui_labels": ui_labels,
        "competition": {"format": competition["format"], "team_structure": structure},
        "capabilities": {key: bool(capabilities.get(key, False)) for key in CAPABILITIES},
        "presentation": presentation,
        "class_scheme": scheme_key,
        "class_metadata": config.get("class_schemes", {}).get(scheme_key, {"classes": []}),
        "goal_pace": goal_pace,
    }


def race_catalog(config: dict[str, Any]) -> list[dict[str, Any]]:
    event_contract(config)
    races = config.get("races")
    if not isinstance(races, list) or not races:
        raise SourceBindingError("races must be a non-empty list")
    seen: set[str] = set()
    for race in races:
        if not isinstance(race, dict):
            raise SourceBindingError("Each race edition must be an object")
        race_key = race.get("race_key")
        missing = [key for key in ("race_key", "race_family", "year", "section", "type", "data_status", "course_version", "route_range", "checkpoint_keys") if race.get(key) in (None, "")]
        if missing:
            raise SourceBindingError(f"Race {race_key or '<missing>'} is missing catalog fields: {', '.join(missing)}")
        if race_key in seen:
            raise SourceBindingError(f"Duplicate race edition {race_key}")
        seen.add(str(race_key))
        if race["data_status"] not in DATA_STATUSES:
            raise SourceBindingError(f"Race {race_key} has invalid data_status {race['data_status']!r}")
        if race["data_status"] == "available" and not isinstance(race.get("source_binding"), dict):
            raise SourceBindingError(f"Race {race_key} is available but has no source_binding")
        race_contract(config, race)
    return races


def resolve_source_bindings(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_events = config.get("source_events", {})
    if not isinstance(source_events, dict):
        raise SourceBindingError("source_events must be an object")

    resolved: dict[str, dict[str, Any]] = {}
    for race in race_catalog(config):
        if race["data_status"] != "available":
            continue
        race_key = race["race_key"]
        reference = race["source_binding"]
        source_event_key = reference.get("source_event")
        source_race_key = reference.get("race")
        source_event = source_events.get(source_event_key)
        if not isinstance(source_event, dict):
            raise SourceBindingError(f"Race {race_key} references unknown source event {source_event_key!r}")
        source_races = source_event.get("race_bindings")
        source_race = source_races.get(source_race_key) if isinstance(source_races, dict) else None
        if not isinstance(source_race, dict):
            raise SourceBindingError(
                f"Race {race_key} references unknown source race {source_race_key!r} in {source_event_key!r}"
            )
        resolved[race_key] = {
            "race": race,
            "source_event_key": source_event_key,
            "source_event": source_event,
            "source_race_key": source_race_key,
            "source_race": source_race,
        }
    return resolved


def group_source_bindings(config: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for race_key, item in resolve_source_bindings(config).items():
        provider = item["source_event"].get("provider")
        if not isinstance(provider, str) or not provider:
            raise SourceBindingError(f"Source event {item['source_event_key']!r} has no provider")
        identity = (provider, item["source_event_key"])
        group = groups.setdefault(identity, {
            "provider": provider,
            "source_event_key": item["source_event_key"],
            "source_event": item["source_event"],
            "bindings": {},
        })
        group["bindings"][race_key] = item
    return [groups[key] for key in sorted(groups)]


def dispatch_source_groups(
    config: dict[str, Any], handlers: dict[str, Callable[[dict[str, Any]], Any]],
) -> list[Any]:
    """Dispatch every available source event once through its provider adapter."""
    outcomes = []
    for group in group_source_bindings(config):
        handler = handlers.get(group["provider"])
        if handler is None:
            raise SourceBindingError(f"No importer registered for provider: {group['provider']}")
        outcomes.append(handler(group))
    return outcomes


def web_race_catalog(config: dict[str, Any], analyzable: set[str] | None = None) -> dict[str, dict[str, Any]]:
    analyzable = analyzable or set()
    resolved = resolve_source_bindings(config)
    return {
        race["race_key"]: {
            "race_key": race["race_key"],
            "event_key": config["event"]["event_key"],
            "race_family": race["race_family"],
            "year": race["year"],
            "race_date": race.get("race_date"),
            "course_version": race.get("course_version"),
            "type": race["type"],
            "section": race["section"],
            "data_status": race["data_status"],
            "source_available": race["race_key"] in resolved,
            "analyzable": race["race_key"] in analyzable,
            **race_contract(config, race),
        }
        for race in race_catalog(config)
    }
