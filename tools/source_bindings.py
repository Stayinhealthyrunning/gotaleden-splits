"""Provider-neutral race catalog and source-binding resolution."""
from __future__ import annotations

from typing import Any, Callable


class SourceBindingError(ValueError):
    pass


DATA_STATUSES = frozenset({"available", "planned"})


def race_catalog(config: dict[str, Any]) -> list[dict[str, Any]]:
    races = config.get("races")
    if not isinstance(races, list) or not races:
        raise SourceBindingError("races must be a non-empty list")
    seen: set[str] = set()
    for race in races:
        if not isinstance(race, dict):
            raise SourceBindingError("Each race edition must be an object")
        race_key = race.get("race_key")
        missing = [key for key in ("race_key", "race_family", "year", "section", "type", "data_status") if race.get(key) in (None, "")]
        if missing:
            raise SourceBindingError(f"Race {race_key or '<missing>'} is missing catalog fields: {', '.join(missing)}")
        if race_key in seen:
            raise SourceBindingError(f"Duplicate race edition {race_key}")
        seen.add(str(race_key))
        if race["data_status"] not in DATA_STATUSES:
            raise SourceBindingError(f"Race {race_key} has invalid data_status {race['data_status']!r}")
        if race["data_status"] == "available" and not isinstance(race.get("source_binding"), dict):
            raise SourceBindingError(f"Race {race_key} is available but has no source_binding")
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
        }
        for race in race_catalog(config)
    }
