"""Resolve provider-neutral race-edition references to configured source bindings."""
from __future__ import annotations

from typing import Any


class SourceBindingError(ValueError):
    pass


def resolve_source_bindings(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_events = config.get("source_events")
    races = config.get("races")
    if not isinstance(source_events, dict) or not source_events:
        raise SourceBindingError("source_events must be a non-empty object")
    if not isinstance(races, list) or not races:
        raise SourceBindingError("races must be a non-empty list")

    resolved: dict[str, dict[str, Any]] = {}
    for race in races:
        race_key = race.get("race_key")
        reference = race.get("source_binding")
        if not race_key or not isinstance(reference, dict):
            raise SourceBindingError(f"Race {race_key or '<missing>'} must declare source_binding")
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
